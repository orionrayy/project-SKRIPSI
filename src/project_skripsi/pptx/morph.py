"""Patch and inspect PowerPoint Morph transitions using Office Open XML.

Morph is stored on the destination slide. For deterministic object matching,
reuse a unique !!name on the corresponding source and destination objects.
The patcher uses only Python's standard library; it does not automate Office.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import posixpath
import re
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable

NS = {
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "p14": "http://schemas.microsoft.com/office/powerpoint/2010/main",
    "p159": "http://schemas.microsoft.com/office/powerpoint/2015/09/main",
}
for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)
SLIDE_RE = re.compile(r"^ppt/slides/slide([1-9][0-9]*)\.xml$")
OPTIONS = {"byObject", "byWord", "byChar"}


def _q(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


def _parts(names: Iterable[str]) -> list[tuple[int, str]]:
    result = []
    for part in names:
        match = SLIDE_RE.match(part)
        if match:
            result.append((int(match.group(1)), part))
    return sorted(result)


def _ordered_slides(archive: zipfile.ZipFile, names: set[str]) -> list[tuple[int, str]]:
    """Resolve displayed slide order and fail closed on malformed metadata."""
    pres_part, rels_part = "ppt/presentation.xml", "ppt/_rels/presentation.xml.rels"
    # Only the complete absence of both order parts permits a numeric fallback.
    if pres_part not in names and rels_part not in names:
        return _parts(names)
    if pres_part not in names or rels_part not in names:
        missing = pres_part if pres_part not in names else rels_part
        raise ValueError(f"Missing presentation slide-order part: {missing}")

    rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    office_rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    try:
        presentation = ET.fromstring(archive.read(pres_part))
    except ET.ParseError as exc:
        raise ValueError(f"Malformed XML in {pres_part}: {exc}") from exc
    try:
        rels = ET.fromstring(archive.read(rels_part))
    except ET.ParseError as exc:
        raise ValueError(f"Malformed XML in {rels_part}: {exc}") from exc

    slide_list = presentation.find(".//p:sldIdLst", NS)
    if slide_list is None:
        return _parts(names)
    slide_ids = slide_list.findall("p:sldId", NS)
    if not slide_ids:
        return _parts(names)

    relationships: dict[str, ET.Element] = {}
    for item in rels.findall(f"{{{rel_ns}}}Relationship"):
        relationship_id = item.get("Id")
        if not relationship_id:
            raise ValueError("Presentation relationship is missing its Id")
        if relationship_id in relationships:
            raise ValueError(f"Duplicate presentation relationship Id: {relationship_id}")
        relationships[relationship_id] = item

    ordered: list[tuple[int, str]] = []
    used_parts: set[str] = set()
    for slide_id in slide_ids:
        relationship_id = slide_id.get(f"{{{office_rel}}}id")
        if not relationship_id:
            raise ValueError("Presentation slide entry is missing its relationship Id")
        relationship = relationships.get(relationship_id)
        if relationship is None:
            raise ValueError(f"Unresolved slide relationship: {relationship_id}")
        if relationship.get("TargetMode") == "External":
            raise ValueError(f"Slide relationship is external: {relationship_id}")
        if not relationship.get("Type", "").endswith("/slide"):
            raise ValueError(f"Relationship is not a slide relationship: {relationship_id}")
        target = relationship.get("Target")
        if not target:
            raise ValueError(f"Slide relationship has no Target: {relationship_id}")

        part = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("ppt", target))
        match = SLIDE_RE.match(part)
        if not match or part not in names:
            raise ValueError(
                f"Slide relationship {relationship_id} targets a missing or invalid slide part: {target!r}"
            )
        if part in used_parts:
            raise ValueError(f"Duplicate slide part in presentation order: {part}")
        used_parts.add(part)
        ordered.append((int(match.group(1)), part))

    if len(ordered) != len(slide_ids):
        raise ValueError("Presentation slide order could not be fully resolved")
    return ordered

def _parse_slide(data: bytes, part: str) -> ET.Element:
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError(f"Malformed XML in {part}: {exc}") from exc


_OBJECT_NV_TAGS = {
    "sp": "nvSpPr",
    "pic": "nvPicPr",
    "graphicFrame": "nvGraphicFramePr",
    "cxnSp": "nvCxnSpPr",
    "grpSp": "nvGrpSpPr",
}


def _forced_objects(root: ET.Element) -> list[tuple[str, str]]:
    """Return forced Morph names with their OOXML object element types.

    The cNvPr record is nested inside the corresponding shape container's
    non-visual properties. Inspecting the parent container type prevents a
    same-name group/shape or picture/shape pair from passing validation.
    """
    result: list[tuple[str, str]] = []
    for element in root.iter():
        object_type = element.tag.rsplit("}", 1)[-1]
        nv_tag = _OBJECT_NV_TAGS.get(object_type)
        if nv_tag is None:
            continue
        nonvisual = element.find(f"p:{nv_tag}/p:cNvPr", NS)
        if nonvisual is None:
            continue
        name = nonvisual.get("name", "")
        if name.startswith("!!"):
            result.append((name, object_type))
    return result


def _names(root: ET.Element) -> list[str]:
    """Compatibility helper returning only the forced names."""
    return [name for name, _ in _forced_objects(root)]


def _morph(root: ET.Element) -> tuple[str | None, int | None, bool]:
    for transition in root.findall(".//p:transition", NS):
        node = transition.find(".//p159:morph", NS)
        if node is None:
            continue
        raw = transition.get(_q("p14", "dur"), transition.get("dur"))
        try:
            duration = int(raw) if raw is not None else None
        except ValueError:
            duration = None
        fallback = root.find(".//mc:AlternateContent/mc:Fallback/p:transition/p:fade", NS) is not None
        return node.get("option"), duration, fallback
    return None, None, False


def _strip_existing_transition_markup(data: bytes) -> bytes:
    """Remove existing direct slide-transition markup without reserializing the slide."""
    alternate_pattern = re.compile(
        rb'<(?P<prefix>(?:[A-Za-z_][\w.-]*:)?)AlternateContent\b[^>]*>.*?</(?P=prefix)AlternateContent\s*>',
        re.DOTALL,
    )
    for match in reversed(list(alternate_pattern.finditer(data))):
        if re.search(rb'<(?:[A-Za-z_][\w.-]*:)?transition\b', match.group(0)):
            data = data[:match.start()] + data[match.end():]

    paired_transition_pattern = re.compile(
        rb'<(?P<prefix>(?:[A-Za-z_][\w.-]*:)?)transition\b[^>]*>.*?</(?P=prefix)transition\s*>',
        re.DOTALL,
    )
    data = paired_transition_pattern.sub(b"", data)
    empty_transition_pattern = re.compile(
        rb'<(?:[A-Za-z_][\w.-]*:)?transition\b[^>]*/\s*>'
    )
    return empty_transition_pattern.sub(b"", data)


def _patch_slide_transition(data: bytes, duration_ms: int, option: str, part: str) -> bytes:
    """Insert PowerPoint-authored Morph markup while preserving all other slide XML bytes.

    The namespace declarations intentionally stay on the MCE Choice and transition
    elements. PowerPoint-authored Morph examples use p159 on mc:Choice and p14 on
    p:transition; the p14 duration attribute does not need p14 in Requires.
    """
    root = _parse_slide(data, part)
    if root.tag != _q("p", "sld"):
        raise ValueError(f"Unexpected slide root element in {part}: {root.tag}")

    slide_prefix = ""
    for _, (prefix, namespace) in ET.iterparse(io.BytesIO(data), events=("start-ns",)):
        if namespace == NS["p"]:
            slide_prefix = prefix
            break

    clean = _strip_existing_transition_markup(data)
    root = _parse_slide(clean, part)
    direct_tags = {child.tag for child in list(root)}
    if _q("p", "clrMapOvr") in direct_tags:
        anchor = "clrMapOvr"
    elif _q("p", "cSld") in direct_tags:
        anchor = "cSld"
    else:
        anchor = None

    pfx = f"{slide_prefix}:" if slide_prefix else ""
    if anchor is not None:
        closing = re.compile(
            rb"</" + re.escape(f"{pfx}{anchor}".encode("ascii")) + rb"\s*>"
        )
        matches = list(closing.finditer(clean))
        if not matches:
            raise ValueError(f"Could not locate closing {anchor} element in {part}")
        insert_at = matches[-1].end()
    else:
        root_close = re.compile(
            rb"</" + re.escape(f"{pfx}sld".encode("ascii")) + rb"\s*>"
        )
        match = root_close.search(clean)
        if not match:
            raise ValueError(f"Could not locate closing slide root in {part}")
        insert_at = match.start()

    fragment = (
        f'<mc:AlternateContent xmlns:mc="{NS["mc"]}" xmlns:p="{NS["p"]}">'
        f'<mc:Choice xmlns:p159="{NS["p159"]}" Requires="p159">'
        f'<p:transition spd="slow" advClick="1" xmlns:p14="{NS["p14"]}" p14:dur="{duration_ms}">'
        f'<p159:morph option="{option}"/>'
        f'</p:transition>'
        f'</mc:Choice>'
        f'<mc:Fallback><p:transition spd="slow" advClick="1"><p:fade/></p:transition></mc:Fallback>'
        f'</mc:AlternateContent>'
    ).encode("utf-8")
    patched = clean[:insert_at] + fragment + clean[insert_at:]
    _parse_slide(patched, part)
    return patched


def apply_morph(
    source: str | Path,
    slide_numbers: Iterable[int],
    *,
    output: str | Path | None = None,
    duration_ms: int = 950,
    option: str = "byObject",
) -> Path:
    """Add Morph to destination slides (1-based presentation order), atomically."""
    src = Path(source).expanduser().resolve()
    dst = Path(output).expanduser().resolve() if output is not None else src
    requested = sorted({int(number) for number in slide_numbers})
    if not requested or any(number < 2 for number in requested):
        raise ValueError("Provide destination slide numbers >= 2")
    if not 1 <= duration_ms <= 30000:
        raise ValueError("duration_ms must be between 1 and 30000")
    if option not in OPTIONS:
        raise ValueError(f"option must be one of {sorted(OPTIONS)}")
    if not src.is_file():
        raise FileNotFoundError(src)

    try:
        with zipfile.ZipFile(src, "r") as archive:
            bad = archive.testzip()
            if bad:
                raise ValueError(f"PPTX ZIP integrity failed at {bad}")
            names = set(archive.namelist())
            slides = _ordered_slides(archive, names)
            if not slides:
                raise ValueError("No PowerPoint slide parts found")
            missing = [number for number in requested if number > len(slides)]
            if missing:
                raise ValueError(f"Destination slide(s) not found in presentation order: {missing}")
            entries = [(info, archive.read(info.filename)) for info in archive.infolist()]
    except zipfile.BadZipFile as exc:
        raise ValueError("Input is not a valid PPTX/ZIP package") from exc

    patched: dict[str, bytes] = {}
    slide_data = {info.filename: data for info, data in entries}
    for display_number in requested:
        _, part = slides[display_number - 1]
        patched[part] = _patch_slide_transition(
            slide_data[part], duration_ms=duration_ms, option=option, part=part
        )

    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{dst.name}.", suffix=".tmp", dir=dst.parent)
    os.close(fd)
    temp = Path(temp_name)
    try:
        with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for info, data in entries:
                archive.writestr(info, patched.get(info.filename, data))
        with zipfile.ZipFile(temp, "r") as archive:
            bad = archive.testzip()
            if bad:
                raise ValueError(f"Patched PPTX ZIP integrity failed at {bad}")
        os.replace(temp, dst)
    except Exception:
        temp.unlink(missing_ok=True)
        raise
    return dst


def inspect_deck(path: str | Path) -> dict:
    """Inspect ZIP integrity, displayed slide order, Morph metadata and object pairs."""
    deck = Path(path).expanduser().resolve()
    if not deck.is_file():
        return {"path": str(deck), "ok": False, "errors": [f"File not found: {deck}"]}
    errors: list[str] = []
    report: list[dict] = []
    try:
        with zipfile.ZipFile(deck, "r") as archive:
            bad = archive.testzip()
            if bad:
                errors.append(f"ZIP CRC check failed at {bad}")
            names = set(archive.namelist())
            if "[Content_Types].xml" not in names or "ppt/presentation.xml" not in names:
                errors.append("Missing required Office Open XML package parts")
            slides = _ordered_slides(archive, names)
            if not slides:
                errors.append("No usable slide sequence found")
                return {"path": str(deck), "ok": False, "slide_count": 0, "morph_slides": [], "slides": [], "errors": errors}
            previous: dict[str, str] = {}
            for display_number, (_, part) in enumerate(slides, start=1):
                root = _parse_slide(archive.read(part), part)
                object_pairs = _forced_objects(root)
                object_names = [name for name, _ in object_pairs]
                object_types = {name: object_type for name, object_type in object_pairs}
                duplicates = sorted({name for name in object_names if object_names.count(name) > 1})
                if duplicates:
                    errors.append(f"Slide {display_number}: duplicate forced object names {duplicates}")
                option, duration, fallback = _morph(root)
                has_morph = option is not None
                morph_requires: list[str] = []
                if has_morph:
                    morph_choice = next(
                        (
                            choice for choice in root.findall(".//mc:AlternateContent/mc:Choice", NS)
                            if choice.find(".//p159:morph", NS) is not None
                        ),
                        None,
                    )
                    if morph_choice is None:
                        errors.append(f"Slide {display_number}: Morph element is not inside mc:Choice")
                    else:
                        morph_requires = sorted(set((morph_choice.get("Requires") or "").split()))
                        if "p159" not in morph_requires:
                            errors.append(f"Slide {display_number}: Morph Choice Requires is missing p159")
                        morph_transition = morph_choice.find(".//p:transition", NS)
                        has_p14_duration = (
                            morph_transition is not None
                            and morph_transition.get(_q("p14", "dur")) is not None
                        )
                        slide_xml = archive.read(part)
                        choice_tag = re.search(rb'<mc:Choice\b[^>]*>', slide_xml)
                        transition_tag = re.search(
                            rb'<mc:Choice\b[^>]*>.*?(<p:transition\b[^>]*>)',
                            slide_xml,
                            re.DOTALL,
                        )
                        if choice_tag is None or f'xmlns:p159="{NS["p159"]}"'.encode() not in choice_tag.group(0):
                            errors.append(
                                f"Slide {display_number}: p159 namespace must be declared on mc:Choice"
                            )
                        if has_p14_duration and (
                            transition_tag is None
                            or f'xmlns:p14="{NS["p14"]}"'.encode() not in transition_tag.group(1)
                        ):
                            errors.append(
                                f"Slide {display_number}: p14 namespace must be declared on the Morph p:transition"
                            )
                    if option not in OPTIONS:
                        errors.append(f"Slide {display_number}: unsupported Morph option {option!r}")
                    if duration is None or duration < 1:
                        errors.append(f"Slide {display_number}: Morph duration missing or invalid")
                    if not fallback:
                        errors.append(f"Slide {display_number}: Fade fallback missing")
                    changed_types = sorted(
                        (name, previous[name], object_type)
                        for name, object_type in object_pairs
                        if name in previous and previous[name] != object_type
                    )
                    for name, prior_type, current_type in changed_types:
                        errors.append(
                            f"Slide {display_number}: forced Morph object {name} changes object type "
                            f"from {prior_type} to {current_type}"
                        )
                    unmatched = sorted(set(object_names) - set(previous))
                    if unmatched:
                        errors.append(f"Slide {display_number}: unpaired Morph objects {unmatched}")
                report.append({
                    "number": display_number, "part": part,
                    "shape_count": len(root.findall(".//p:cNvPr", NS)),
                    "forced_object_names": object_names,
                    "forced_object_types": [{"name": name, "object_type": kind} for name, kind in object_pairs],
                    "morph": has_morph,
                    "morph_option": option, "duration_ms": duration, "fade_fallback": fallback,
                    "morph_requires": morph_requires,
                })
                previous = object_types
    except (zipfile.BadZipFile, OSError, ValueError, ET.ParseError) as exc:
        errors.append(str(exc))
        return {"path": str(deck), "ok": False, "errors": errors}
    morph_slides = [item["number"] for item in report if item["morph"]]
    return {
        "path": str(deck), "ok": not errors, "slide_count": len(report),
        "morph_slides": morph_slides,
        "forced_object_count": sum(len(item["forced_object_names"]) for item in report),
        "slides": report, "errors": errors,
    }


def _parse_slide_list(value: str) -> list[int]:
    try:
        numbers = [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use comma-separated display slide numbers, e.g. 5,7,9") from exc
    if not numbers or any(number < 2 for number in numbers):
        raise argparse.ArgumentTypeError("Provide destination slide numbers >= 2")
    return numbers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect and patch PowerPoint Morph transitions.")
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect", help="Validate PPTX structure and object matching")
    inspect.add_argument("deck", type=Path)
    apply = sub.add_parser("apply", help="Add Morph to destination slides")
    apply.add_argument("source", type=Path)
    apply.add_argument("--slides", type=_parse_slide_list, required=True)
    apply.add_argument("--output", type=Path, help="Write a separate copy; default patches in place")
    apply.add_argument("--duration-ms", type=int, default=950)
    apply.add_argument("--option", choices=sorted(OPTIONS), default="byObject")
    args = parser.parse_args(argv)
    try:
        if args.command == "apply":
            path = apply_morph(args.source, args.slides, output=args.output, duration_ms=args.duration_ms, option=args.option)
            result = inspect_deck(path)
        else:
            result = inspect_deck(args.deck)
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 2
    except (OSError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
