"""Privacy-minimizing rendered-PDF composition diagnostics.

Static PDF geometry proxies are not gaze, comprehension, attention span,
motif quality or aesthetic acceptance. Human review remains a separate gate.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

try:
    import fitz
except ImportError:  # pragma: no cover
    fitz = None  # type: ignore[assignment]


class VisualCompositionAuditError(ValueError):
    """Invalid PDF or policy supplied to the visual composition auditor."""


def _area(rect: Any) -> float:
    return max(0.0, float(rect.width)) * max(0.0, float(rect.height))


def _union_area(rectangles: list[Any]) -> float:
    """Calculate union area of axis-aligned text span rectangles."""
    values = []
    edges: set[float] = set()
    for r in rectangles:
        x0, y0, x1, y1 = map(float, (r.x0, r.y0, r.x1, r.y1))
        if x1 > x0 and y1 > y0:
            values.append((x0, y0, x1, y1))
            edges.update((x0, x1))
    xs = sorted(edges)
    total = 0.0
    for left, right in zip(xs, xs[1:]):
        if right <= left:
            continue
        mid = (left + right) / 2
        spans = sorted((y0, y1) for x0, y0, x1, y1 in values if x0 < mid < x1)
        if not spans:
            continue
        y0, y1 = spans[0]
        height = 0.0
        for a, b in spans[1:]:
            if a <= y1:
                y1 = max(y1, b)
            else:
                height += y1 - y0
                y0, y1 = a, b
        total += (right - left) * (height + y1 - y0)
    return total


def _page_metrics(page: Any, policy: dict[str, Any]) -> dict[str, Any]:
    rect = page.rect
    page_area = _area(rect) or 1.0
    text_rects: list[Any] = []
    sizes: list[float] = []
    fonts: Counter[str] = Counter()
    blocks = lines = spans = 0
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        found_block = False
        for line in block.get("lines", []):
            found_line = False
            for span in line.get("spans", []):
                value = str(span.get("text", ""))
                if not value.strip():
                    continue
                found_block = found_line = True
                spans += 1
                size = float(span.get("size", 0) or 0)
                if size > 0:
                    sizes.append(round(size * 2) / 2)
                fonts[str(span.get("font", "unknown"))] += len(value)
                bbox = span.get("bbox")
                if bbox:
                    text_rects.append(fitz.Rect(*bbox))
            lines += int(found_line)
        blocks += int(found_block)
    union = _union_area(text_rects)
    if text_rects:
        bounds = fitz.Rect(min(r.x0 for r in text_rects), min(r.y0 for r in text_rects),
                           max(r.x1 for r in text_rects), max(r.y1 for r in text_rects))
        bounds_ratio = min(1.0, _area(bounds) / page_area)
        margins = {
            "top": max(0.0, bounds.y0 / max(1.0, rect.height)),
            "right": max(0.0, (rect.width - bounds.x1) / max(1.0, rect.width)),
            "bottom": max(0.0, (rect.height - bounds.y1) / max(1.0, rect.height)),
            "left": max(0.0, bounds.x0 / max(1.0, rect.width)),
        }
    else:
        bounds_ratio = 0.0
        margins = {key: 0.0 for key in ("top", "right", "bottom", "left")}

    threshold = float(policy.get("heading_min_size_pt", 14.0))
    heading = [x for x in sizes if x >= threshold]
    body = [x for x in sizes if x < threshold] or sizes
    hm = median(heading) if heading else None
    bm = median(body) if body else None
    ratio = round(hm / bm, 3) if hm and bm and bm > 0 else None

    drawings: Counter[str] = Counter()
    rect_areas = []
    for drawing in page.get_drawings():
        for item in drawing.get("items", []):
            kind = str(item[0]) if item else "unknown"
            drawings[kind] += 1
            if kind == "re" and len(item) > 1:
                value = _area(item[1])
                if value > 0:
                    rect_areas.append(round(value / page_area, 4))
    repeated = max(Counter(rect_areas).values(), default=0)
    return {
        "page_number": page.number + 1,
        "page_size_pt": [round(rect.width, 2), round(rect.height, 2)],
        "text_area_ratio": round(min(1.0, union / page_area), 4),
        "text_content_bounds_ratio": round(bounds_ratio, 4),
        "margin_band_ratios": {k: round(v, 4) for k, v in margins.items()},
        "text_block_count": blocks,
        "text_line_count": lines,
        "text_span_count": spans,
        "distinct_font_size_count": len(set(sizes)),
        "font_sizes_pt": sorted(set(sizes)),
        "body_median_font_size_pt": round(bm, 2) if bm else None,
        "heading_median_font_size_pt": round(hm, 2) if hm else None,
        "heading_body_size_ratio": ratio,
        "font_families": sorted(fonts),
        "rectangle_shape_count": drawings.get("re", 0),
        "repeated_rectangle_size_max_count": repeated,
        "drawing_item_counts": dict(sorted(drawings.items())),
        "embedded_image_count": len(page.get_images(full=True)),
    }


def _validate_policy(policy: dict[str, Any]) -> None:
    low, high = policy.get("min_text_area_ratio"), policy.get("max_text_area_ratio")
    if low is not None and high is not None and float(low) > float(high):
        raise VisualCompositionAuditError("min_text_area_ratio cannot exceed max_text_area_ratio")
    for key in ("density_severity", "hierarchy_severity", "shape_severity"):
        if key in policy and policy[key] not in {"WARNING", "ERROR"}:
            raise VisualCompositionAuditError(f"{key} must be WARNING or ERROR")
    allowed_task_states = {"NOT_RUN", "PASS", "WARN", "FAIL", "NOT_APPLICABLE"}
    if policy.get("reader_task_test_status", "NOT_RUN") not in allowed_task_states:
        raise VisualCompositionAuditError("unsupported reader_task_test_status")
    if "profile_id" in policy and (not isinstance(policy["profile_id"], str) or not policy["profile_id"].strip()):
        raise VisualCompositionAuditError("profile_id must be a non-empty string")


def _finding(code: str, severity: str, page: int, message: str) -> dict[str, Any]:
    return {"code": code, "severity": severity, "page_number": page, "message": message}


def audit_visual_composition(pdf_path: str | Path, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    """Audit a rendered PDF using explicit, profile-specific geometry proxies.

    The report omits PDF path, filename, extracted text, identifiers and hashes.
    An unconfigured or zero-threshold audit returns WARN, not PASS.
    """
    if fitz is None:
        raise VisualCompositionAuditError("PyMuPDF is required; install project-skripsi-engine[pdf-qa]")
    policy = dict(policy or {})
    _validate_policy(policy)
    path = Path(pdf_path).expanduser().resolve(strict=True)
    if not path.is_file() or path.suffix.casefold() != ".pdf":
        raise VisualCompositionAuditError("input must be an existing PDF file")

    findings: list[dict[str, Any]] = []
    pages: list[dict[str, Any]] = []
    with fitz.open(path) as pdf:
        if pdf.is_encrypted or len(pdf) == 0:
            raise VisualCompositionAuditError("PDF must be non-empty and unencrypted")
        for page in pdf:
            m = _page_metrics(page, policy)
            pages.append(m)
            n = m["page_number"]
            low, high = policy.get("min_text_area_ratio"), policy.get("max_text_area_ratio")
            if low is not None and m["text_area_ratio"] < float(low):
                findings.append(_finding("PAGE_TEXT_DENSITY_BELOW_PROFILE", policy.get("density_severity", "WARNING"), n,
                    "Text geometry is below this profile range; inspect whether whitespace is intentional or the page is under-filled."))
            if high is not None and m["text_area_ratio"] > float(high):
                findings.append(_finding("PAGE_TEXT_DENSITY_ABOVE_PROFILE", policy.get("density_severity", "WARNING"), n,
                    "Text geometry is above this profile range; inspect crowding, line length and paragraph grouping."))
            if "min_distinct_font_sizes" in policy and m["distinct_font_size_count"] < int(policy["min_distinct_font_sizes"]):
                findings.append(_finding("TYPOGRAPHIC_HIERARCHY_TOO_FLAT", policy.get("hierarchy_severity", "WARNING"), n,
                    "Fewer font-size levels than configured; inspect whether title, section, label and body roles are distinguishable."))
            minimum_ratio = policy.get("min_heading_body_size_ratio")
            if minimum_ratio is not None and (m["heading_body_size_ratio"] is None or m["heading_body_size_ratio"] < float(minimum_ratio)):
                findings.append(_finding("HEADING_BODY_CONTRAST_LOW", policy.get("hierarchy_severity", "WARNING"), n,
                    "Approximate heading/body size contrast is below the profile threshold or cannot be established."))
            max_rects = policy.get("max_rectangle_shapes_per_page")
            if max_rects is not None and m["rectangle_shape_count"] > int(max_rects):
                findings.append(_finding("RECTANGULAR_SHAPE_OVERUSE", policy.get("shape_severity", "WARNING"), n,
                    "More rectangular vector objects than this profile allows; inspect repeated cards, panels and frames."))
            max_repeat = policy.get("max_repeated_rectangle_size_count")
            if max_repeat is not None and m["repeated_rectangle_size_max_count"] > int(max_repeat):
                findings.append(_finding("REPEATED_BOX_GEOMETRY", policy.get("shape_severity", "WARNING"), n,
                    "Several rectangular shapes share a near-identical area; inspect repetitive box geometry."))

    errors = sum(x["severity"] == "ERROR" for x in findings)
    warnings = sum(x["severity"] == "WARNING" for x in findings)
    keys = ("min_text_area_ratio", "max_text_area_ratio", "min_distinct_font_sizes",
            "min_heading_body_size_ratio", "max_rectangle_shapes_per_page", "max_repeated_rectangle_size_count")
    threshold_count = sum(key in policy for key in keys)
    status = "FAIL" if errors else "WARN" if warnings or threshold_count == 0 else "PASS"
    return {
        "schema_version": "1.0.0",
        "status": status,
        "audited_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "assessment_scope": "PDF_LAYOUT_PROXIES_ONLY_NOT_EYE_TRACKING_OR_AESTHETIC_ACCEPTANCE",
        "profile_id": policy.get("profile_id"),
        "reader_attention": {
            "eye_tracking_status": "NOT_MEASURED",
            "reader_task_test_status": policy.get("reader_task_test_status", "NOT_RUN"),
            "note": "Gaze, attention duration, comprehension and preference require direct human evidence; static PDF geometry does not infer them."
        },
        "summary": {"page_count": len(pages), "error_count": errors, "warning_count": warnings,
                    "policy_threshold_count": threshold_count},
        "pages": pages,
        "findings": findings,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Audit PDF composition using privacy-minimizing layout proxies")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        policy = json.loads(args.policy.read_text(encoding="utf-8")) if args.policy else {}
        if not isinstance(policy, dict):
            raise VisualCompositionAuditError("policy root must be an object")
        report = audit_visual_composition(args.pdf, policy)
        payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            if args.output.exists() or args.output.is_symlink():
                raise FileExistsError(f"refusing to overwrite existing report: {args.output}")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload, encoding="utf-8", newline="\n")
        print(payload, end="")
        return 1 if report["status"] == "FAIL" else 0
    except (OSError, json.JSONDecodeError, VisualCompositionAuditError) as exc:
        parser.exit(2, f"error: {exc}\n")
        