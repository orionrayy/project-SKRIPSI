#!/usr/bin/env python3
"""Download and audit the 22 priority A+B Morph references; retain reports, not PPTX media."""
from __future__ import annotations

import concurrent.futures
import csv
import hashlib
import json
import posixpath
import re
import tempfile
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/visuals/morph-dataset/priority_A_B_shortlist.csv"
REPORT = ROOT / "reports/morph-dataset-verification.json"
NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}
SHAPE_TAGS = {
    "sp": "nvSpPr",
    "pic": "nvPicPr",
    "graphicFrame": "nvGraphicFramePr",
    "cxnSp": "nvCxnSpPr",
    "grpSp": "nvGrpSpPr",
}
INTEGER_FIELDS = (
    "size_bytes", "physical_slide_parts", "slide_count", "orphan_slide_parts",
    "morph_slide_count", "active_morph_pairs", "pairs_with_name_match",
    "pairs_with_geometry_changes", "pairs_without_name_match",
    "matched_object_pairs", "geometry_changed_object_pairs",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def slide_shapes(root: ET.Element):
    shapes = []
    for kind, nv_tag in SHAPE_TAGS.items():
        for node in root.findall(f".//p:{kind}", NS):
            nv = node.find(f"p:{nv_tag}", NS)
            props = nv.find("p:cNvPr", NS) if nv is not None else None
            if props is None:
                continue
            shape_props = next(
                (child for child in list(node)
                 if child.tag.endswith("spPr") or child.tag.endswith("grpSpPr")),
                None,
            )
            xfrm = shape_props.find("a:xfrm", NS) if shape_props is not None else None
            geometry = None
            if xfrm is not None:
                off, ext = xfrm.find("a:off", NS), xfrm.find("a:ext", NS)
                if off is not None and ext is not None:
                    geometry = (
                        off.get("x", ""), off.get("y", ""),
                        ext.get("cx", ""), ext.get("cy", ""),
                        xfrm.get("rot", "0"),
                    )
            shapes.append((kind, props.get("name", ""), geometry))
    return shapes


def active_slide_order(archive: zipfile.ZipFile) -> list[str]:
    presentation = ET.fromstring(archive.read("ppt/presentation.xml"))
    relationships = ET.fromstring(archive.read("ppt/_rels/presentation.xml.rels"))
    targets = {item.get("Id"): item.get("Target") for item in relationships}
    names = set(archive.namelist())
    ordered = []
    for slide_id in presentation.findall(".//p:sldId", NS):
        target = targets.get(slide_id.get(f"{{{NS['r']}}}id"))
        if not target:
            continue
        part = (
            posixpath.normpath(target.lstrip("/"))
            if target.startswith("/")
            else posixpath.normpath(posixpath.join("ppt", target))
        )
        if part in names:
            ordered.append(part)
    return ordered


def audit(archive: zipfile.ZipFile) -> dict:
    names = set(archive.namelist())
    physical = [
        name for name in names
        if name.startswith("ppt/slides/slide") and name.endswith(".xml")
    ]
    order = active_slide_order(archive)
    slides = []
    options = Counter()
    for part in order:
        data = archive.read(part)
        has_morph = b"p159:morph" in data
        for value in re.findall(rb'<p159:morph[^>]*option=["\\']([^"\\']+)', data):
            options[value.decode("utf-8", "replace")] += 1
        slides.append((has_morph, slide_shapes(ET.fromstring(data))))

    active_pairs = pairs_with_match = pairs_with_geometry = pairs_without_match = 0
    matched_objects = changed_objects = 0
    for index in range(1, len(slides)):
        destination_has_morph, destination = slides[index]
        if not destination_has_morph:
            continue
        active_pairs += 1
        previous = slides[index - 1][1]
        previous_counts = Counter((kind, name) for kind, name, _ in previous if name)
        destination_counts = Counter((kind, name) for kind, name, _ in destination if name)
        common = set(previous_counts) & set(destination_counts)
        unique = [
            key for key in common
            if previous_counts[key] == 1 and destination_counts[key] == 1
        ]
        previous_map = {
            (kind, name): geometry for kind, name, geometry in previous
            if name and previous_counts[(kind, name)] == 1
        }
        destination_map = {
            (kind, name): geometry for kind, name, geometry in destination
            if name and destination_counts[(kind, name)] == 1
        }
        changed = [key for key in unique if previous_map[key] != destination_map[key]]
        matched_objects += len(unique)
        changed_objects += len(changed)
        if unique:
            pairs_with_match += 1
        else:
            pairs_without_match += 1
        if changed:
            pairs_with_geometry += 1

    return {
        "physical_slide_parts": len(physical),
        "slide_count": len(order),
        "orphan_slide_parts": len(set(physical) - set(order)),
        "morph_slide_count": sum(1 for flag, _ in slides if flag),
        "active_morph_pairs": active_pairs,
        "pairs_with_name_match": pairs_with_match,
        "pairs_with_geometry_changes": pairs_with_geometry,
        "pairs_without_name_match": pairs_without_match,
        "matched_object_pairs": matched_objects,
        "geometry_changed_object_pairs": changed_objects,
        "morph_options": dict(sorted(options.items())),
    }


def download_and_verify(record: dict, workspace: Path) -> dict:
    url = record["download_url"]
    target = workspace / f'{record["id"]}.pptx'
    result = {"id": record["id"], "filename": record["filename"], "url": url}
    error = None
    for attempt in range(1, 4):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "project-SKRIPSI-morph-dataset-audit/1.0",
                    "Accept": "application/octet-stream",
                },
            )
            with urllib.request.urlopen(request, timeout=90) as response, target.open("wb") as out:
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    out.write(block)
            break
        except Exception as exc:
            error = repr(exc)
            target.unlink(missing_ok=True)
            if attempt < 3:
                time.sleep(2 * attempt)
    else:
        return {**result, "status": "DOWNLOAD_FAILED", "error": error}

    result["size_bytes"] = target.stat().st_size
    if result["size_bytes"] != int(record["size_bytes"]):
        return {**result, "status": "SIZE_MISMATCH", "expected_size": int(record["size_bytes"])}
    result["sha256"] = sha256(target)
    if result["sha256"].lower() != record["sha256"].lower():
        return {**result, "status": "HASH_MISMATCH"}

    try:
        with zipfile.ZipFile(target) as archive:
            bad_member = archive.testzip()
            if bad_member:
                return {**result, "status": "ZIP_CRC_FAIL", "bad_member": bad_member}
            observed = audit(archive)
    except Exception as exc:
        return {**result, "status": "PPTX_PARSE_FAILED", "error": repr(exc)}

    mismatches = {}
    for field in INTEGER_FIELDS:
        if field == "size_bytes":
            continue
        expected = int(record[field])
        actual = observed[field]
        if expected != actual:
            mismatches[field] = {"expected": expected, "actual": actual}
    expected_options = sorted(
        value for value in record["morph_options"].split(";") if value
    )
    if expected_options != sorted(observed["morph_options"]):
        mismatches["morph_options"] = {
            "expected": expected_options,
            "actual": sorted(observed["morph_options"]),
        }
    if mismatches:
        return {**result, "status": "AUDIT_MISMATCH", "mismatches": mismatches}
    return {
        **result,
        "status": "PASS",
        "zip_crc": "PASS",
        "active_slide_count": observed["slide_count"],
        "morph_slide_count": observed["morph_slide_count"],
        "active_morph_pairs": observed["active_morph_pairs"],
        "matched_object_pairs": observed["matched_object_pairs"],
        "geometry_changed_object_pairs": observed["geometry_changed_object_pairs"],
    }


def main() -> int:
    with MANIFEST.open(encoding="utf-8-sig", newline="") as stream:
        records = list(csv.DictReader(stream))
    if len(records) != 22:
        raise RuntimeError(f"Expected 22 priority A+B records, found {len(records)}")
    if len({row["sha256"] for row in records}) != len(records):
        raise RuntimeError("Duplicate SHA-256 values detected in priority shortlist")
    if any(row["priority"] not in {"A", "B"} for row in records):
        raise RuntimeError("Priority shortlist contains a record outside A+B")

    with tempfile.TemporaryDirectory(prefix="morph-pptx-audit-") as tmp:
        workspace = Path(tmp)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda row: download_and_verify(row, workspace), records))

    passed = sum(item["status"] == "PASS" for item in results)
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_manifest": str(MANIFEST.relative_to(ROOT)),
        "expected_count": len(records),
        "passed": passed,
        "failed": len(results) - passed,
        "binary_retention": "NONE; temporary downloads deleted after verification",
        "results": results,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, indent=2))
    for item in results:
        if item["status"] != "PASS":
            print(item["id"], item["status"], item.get("error", item.get("mismatches", "")))
    return 0 if passed == len(records) else 2


if __name__ == "__main__":
    raise SystemExit(main())
