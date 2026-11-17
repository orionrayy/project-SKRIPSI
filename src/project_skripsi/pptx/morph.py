"""Patch and inspect PowerPoint Morph transitions using Office Open XML.

Morph is stored on the destination slide. For deterministic object matching,
reuse a unique !!name on the corresponding source and destination objects.
The patcher uses only Python's standard library; it does not automate Office.
"""
from __future__ import annotations

import argparse
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
    """Resolve displayed slide order through presentation relationships."""
    pres_part, rels_part = "ppt/presentation.xml", "ppt/_rels/presentation.xml.rels"
    if pres_part not in names or rels_part not in names:
        return _parts(names)
    try:
        presentation = ET.fromstring(archive.read(pres_part))
        rels = ET.fromstring(archive.read(rels_part))
        rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
        office_rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        targets = {
            item.get("Id"): item.get("Target")
            for item in rels.findall(f"{{{rel_ns}}}Relationship")
            if item.get("Type", "").endswith("/slide") and item.get("TargetMode") != "External"
        }
        ordered = []
        for slide_id in presentation.findall(".//p:sldIdLst/p:sldId", NS):
            target = targets.get(slide_id.get(f"{{{office_rel}}}id"))
            if not target:
                continue
            part = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("ppt", target))
            match = SLIDE_RE.match(part)
            if match and part in names:
                ordered.append((int(match.group(1)), part))
        if ordered:
            return ordered
    except ET.ParseError:
        pass
    return _parts(names)


def _parse_slide(data: bytes, part: str) -> ET.Element:
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError(f"Malformed XML in {part}: {exc}") from exc


def _names(root: ET.Element) -> list[str]:
    return [node.get("name", "") for node in root.findall(".//p:cNvPr", NS) if node.get("name", "").startswith("!!")]


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
    for display_number in requested:
        _, part = slides[display_number - 1]
        root = _parse_slide(next(data for info, data in entries if info.filename == part), part)
        for child in list(root):
            local = child.tag.rsplit("}", 1)[-1]
            if local == "transition" or (local == "AlternateContent" and child.find(".//p:transition", NS) is not None):
                root.remove(child)
        alternate = ET.Element(_q("mc", "AlternateContent"))
        choice = ET.SubElement(alternate, _q("mc", "Choice"), {"Requires": "p159"})
        transition = ET.SubElement(choice, _q("p", "transition"), {
            "spd": "slow", "advClick": "1", _q("p14", "dur"): str(duration_ms)
        })
        ET.SubElement(transition, _q("p159", "morph"), {"option": option})
        fallback = ET.SubElement(alternate, _q("mc", "Fallback"))
        fade = ET.SubElement(fallback, _q("p", "transition"), {"spd": "slow", "advClick": "1"})
        ET.SubElement(fade, _q("p", "fade"))
        insert_at = next((i for i, child in enumerate(root) if child.tag in {_q("p", "timing"), _q("p", "extLst")}), len(root))
        root.insert(insert_at, alternate)
        patched[part] = ET.tostring(root, encoding="utf-8", xml_declaration=True)

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
            previous: list[str] = []
            for display_number, (_, part) in enumerate(slides, start=1):
                root = _parse_slide(archive.read(part), part)
                object_names = _names(root)
                duplicates = sorted({name for name in object_names if object_names.count(name) > 1})
                if duplicates:
                    errors.append(f"Slide {display_number}: duplicate forced object names {duplicates}")
                option, duration, fallback = _morph(root)
                has_morph = option is not None
                if has_morph:
                    if option not in OPTIONS:
                        errors.append(f"Slide {display_number}: unsupported Morph option {option!r}")
                    if duration is None or duration < 1:
                        errors.append(f"Slide {display_number}: Morph duration missing or invalid")
                    if not fallback:
                        errors.append(f"Slide {display_number}: Fade fallback missing")
                    unmatched = sorted(set(object_names) - set(previous))
                    if unmatched:
                        errors.append(f"Slide {display_number}: unpaired Morph objects {unmatched}")
                report.append({
                    "number": display_number, "part": part,
                    "shape_count": len(root.findall(".//p:cNvPr", NS)),
                    "forced_object_names": object_names, "morph": has_morph,
                    "morph_option": option, "duration_ms": duration, "fade_fallback": fallback,
                })
                previous = object_names
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
