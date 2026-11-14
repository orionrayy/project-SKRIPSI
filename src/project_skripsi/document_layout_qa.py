"""Privacy-minimizing QA for rendered academic DOCX/PDF layout pairs.

The auditor reports structural metrics and page-number/layout findings only.
It deliberately does not persist manuscript text, names, IDs, or source passages.
"""
from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import fitz
except ImportError:  # pragma: no cover - optional dependency
    fitz = None  # type: ignore[assignment]

try:
    from docx import Document
    from docx.oxml.ns import qn
except ImportError:  # pragma: no cover - optional dependency
    Document = None  # type: ignore[assignment]
    qn = None  # type: ignore[assignment]


class DocumentLayoutAuditError(ValueError):
    """Raised when the supplied document pair or policy cannot be audited."""


PAGE_SIZE_POINTS = {
    "A4": (595.276, 841.890),
    "LETTER": (612.0, 792.0),
}


def _normalise_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _part_text(part: Any) -> str:
    return " ".join(p.text for p in part.paragraphs if p.text).strip()


def _page_fields(part: Any) -> int:
    root = part._element
    count = 0
    for node in root.iter():
        if qn is not None and node.tag == qn("w:instrText"):
            if "PAGE" in (node.text or "").upper():
                count += 1
        elif qn is not None and node.tag == qn("w:fldSimple"):
            if "PAGE" in (node.get(qn("w:instr")) or "").upper():
                count += 1
    return count


def _section_start_number(section: Any) -> int | None:
    node = section._sectPr.find(qn("w:pgNumType"))
    if node is None:
        return None
    value = node.get(qn("w:start"))
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _extract_docx_metrics(path: Path) -> dict[str, Any]:
    if Document is None or qn is None:
        raise DocumentLayoutAuditError("python-docx is required; install project-skripsi-engine[docx]")
    with zipfile.ZipFile(path) as archive:
        bad_member = archive.testzip()
        if bad_member:
            raise DocumentLayoutAuditError(f"DOCX package CRC failure: {bad_member}")
        names = set(archive.namelist())
        if "word/document.xml" not in names or "[Content_Types].xml" not in names:
            raise DocumentLayoutAuditError("DOCX is missing mandatory OOXML package parts")

    document = Document(path)
    sections: list[dict[str, Any]] = []
    for index, section in enumerate(document.sections):
        width_pt = float(section.page_width.pt)
        height_pt = float(section.page_height.pt)
        if width_pt > height_pt:
            orientation = "LANDSCAPE"
        else:
            orientation = "PORTRAIT"
        sections.append({
            "index": index,
            "page_width_pt": round(width_pt, 2),
            "page_height_pt": round(height_pt, 2),
            "orientation": orientation,
            "margins_cm": {
                "top": round(float(section.top_margin.cm), 3),
                "right": round(float(section.right_margin.cm), 3),
                "bottom": round(float(section.bottom_margin.cm), 3),
                "left": round(float(section.left_margin.cm), 3),
            },
            "different_first_page_header_footer": bool(section.different_first_page_header_footer),
            "start_page_number": _section_start_number(section),
            "default_footer_text_present": bool(_part_text(section.footer)),
            "first_page_footer_text_present": bool(_part_text(section.first_page_footer)),
            "default_footer_page_fields": _page_fields(section.footer),
            "first_page_footer_page_fields": _page_fields(section.first_page_footer),
            "default_header_page_fields": _page_fields(section.header),
            "first_page_header_page_fields": _page_fields(section.first_page_header),
        })

    normal = document.styles["Normal"]
    font_families: set[str] = set()
    font_sizes: set[float] = set()
    if normal.font.name:
        font_families.add(normal.font.name)
    if normal.font.size:
        font_sizes.add(round(float(normal.font.size.pt), 2))
    headings = []
    missing_alt: list[str] = []
    for paragraph in document.paragraphs:
        if paragraph.style and paragraph.style.name.startswith("Heading") and paragraph.text.strip():
            headings.append(paragraph.text.strip())
        for run in paragraph.runs:
            if run.font.name:
                font_families.add(run.font.name)
            if run.font.size:
                font_sizes.add(round(float(run.font.size.pt), 2))
    for shape in document.inline_shapes:
        try:
            docpr = shape._inline.docPr
            if not (docpr.get("descr") or "").strip():
                missing_alt.append(str(docpr.get("id") or "unknown"))
        except Exception:
            missing_alt.append("unknown")

    return {
        "section_count": len(sections),
        "sections": sections,
        "normal_style": {
            "font_family": normal.font.name,
            "font_size_pt": round(float(normal.font.size.pt), 2) if normal.font.size else None,
            "line_spacing": round(float(normal.paragraph_format.line_spacing), 3)
            if isinstance(normal.paragraph_format.line_spacing, (int, float)) else None,
            "first_line_indent_cm": round(float(normal.paragraph_format.first_line_indent.cm), 3)
            if normal.paragraph_format.first_line_indent else 0.0,
        },
        "observed_font_families": sorted(font_families),
        "observed_font_sizes_pt": sorted(font_sizes),
        "heading_count": len(headings),
        "table_count": len(document.tables),
        "inline_image_count": len(document.inline_shapes),
        "images_missing_alt_count": len(missing_alt),
    }


def _footer_tokens(page: Any, policy: dict[str, Any]) -> list[str]:
    height = float(page.rect.height)
    width = float(page.rect.width)
    y_fraction = float(policy.get("footer_band_start", 0.90))
    position = policy.get("page_number_position", "BOTTOM_CENTER")
    tokens: list[str] = []
    for word in page.get_text("words"):
        x0, y0, x1, _y1, text = word[:5]
        if float(y0) < height * y_fraction:
            continue
        x_center = (float(x0) + float(x1)) / 2.0
        x_fraction = x_center / width if width else 0.5
        if position == "BOTTOM_CENTER" and not 0.30 <= x_fraction <= 0.70:
            continue
        if position == "BOTTOM_RIGHT" and x_fraction < 0.65:
            continue
        if position == "BOTTOM_LEFT" and x_fraction > 0.35:
            continue
        clean = str(text).strip().strip("()[]")
        if re.fullmatch(r"\d{1,4}", clean):
            tokens.append(clean)
    return tokens


def _top_heading_present(page: Any, heading: str) -> bool:
    """Find a heading in the top 42% while excluding dotted-TOC leader rows."""
    target = _normalise_text(heading)
    if not target:
        return False
    blocks = page.get_text("blocks")
    lines: list[str] = []
    for block in sorted(blocks, key=lambda item: (item[1], item[0])):
        x0, y0, _x1, _y1, text = block[:5]
        if float(y0) > float(page.rect.height) * 0.42:
            continue
        for line in str(text).splitlines():
            candidate = line.strip()
            if not candidate or re.search(r"\.{2,}", candidate):
                continue
            lines.append(candidate)
    combined = _normalise_text(" ".join(lines))
    return target in combined


def _add_finding(findings: list[dict[str, str]], code: str, severity: str, message: str) -> None:
    findings.append({"code": code, "severity": severity, "message": message})


def audit_document_layout(
    docx_path: str | Path,
    pdf_path: str | Path,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Audit a DOCX/PDF pair against formatting and pagination requirements.

    `policy` supports page_size, margins_cm, font_family, font_size_pt,
    line_spacing, cover_pages, body_start_number, page_number_position,
    footer_band_start, require_dedicated_cover_section, expected_page_count,
    min_page_text_chars, and expected_page_map (heading -> displayed number).
    """
    if fitz is None:
        raise DocumentLayoutAuditError("PyMuPDF is required; install project-skripsi-engine[pdf-qa]")
    policy = dict(policy or {})
    docx = Path(docx_path).expanduser().resolve(strict=True)
    pdf = Path(pdf_path).expanduser().resolve(strict=True)
    if docx.suffix.casefold() != ".docx" or not docx.is_file():
        raise DocumentLayoutAuditError("DOCX input must be an existing .docx file")
    if pdf.suffix.casefold() != ".pdf" or not pdf.is_file():
        raise DocumentLayoutAuditError("PDF input must be an existing .pdf file")

    findings: list[dict[str, str]] = []
    docx_metrics = _extract_docx_metrics(docx)
    with fitz.open(pdf) as pdf_doc:
        if pdf_doc.is_encrypted:
            raise DocumentLayoutAuditError("encrypted PDF cannot be audited")
        pages = list(pdf_doc)
        page_count = len(pages)
        if page_count < 1:
            raise DocumentLayoutAuditError("PDF contains no pages")
        page_text_lengths = [len(page.get_text("text").strip()) for page in pages]
        footer_tokens = [_footer_tokens(page, policy) for page in pages]
        pdf_metrics = {
            "page_count": page_count,
            "page_text_character_counts": page_text_lengths,
            "footer_number_tokens": footer_tokens,
        }
        if policy.get("expected_page_count") is not None and page_count != int(policy["expected_page_count"]):
            _add_finding(findings, "PDF_PAGE_COUNT_MISMATCH", "ERROR", f"Expected {policy['expected_page_count']} pages; found {page_count}.")

        cover_pages = int(policy.get("cover_pages", 1))
        body_start_number = int(policy.get("body_start_number", 1))
        if cover_pages < 0 or cover_pages >= page_count:
            _add_finding(findings, "INVALID_COVER_PAGE_COUNT", "ERROR", "cover_pages must be non-negative and smaller than the PDF page count.")
            cover_pages = max(0, min(cover_pages, page_count - 1))
        for index in range(cover_pages):
            if footer_tokens[index]:
                _add_finding(findings, "COVER_PAGE_NUMBER_VISIBLE", "ERROR", f"A page-number candidate is visible in the footer area of cover page {index + 1}.")
        detected_body_numbers: list[int | None] = []
        for physical_index in range(cover_pages, page_count):
            expected = body_start_number + (physical_index - cover_pages)
            tokens = footer_tokens[physical_index]
            parsed = [int(token) for token in tokens]
            detected = expected if expected in parsed else (parsed[0] if len(parsed) == 1 else None)
            detected_body_numbers.append(detected)
            if expected not in parsed:
                if not tokens:
                    reason = "no page number was detected"
                else:
                    reason = "detected footer number(s): " + ", ".join(tokens)
                _add_finding(findings, "BODY_PAGE_NUMBER_SEQUENCE_MISMATCH", "ERROR", f"Physical page {physical_index + 1} should display {expected}; {reason}.")

        minimum_chars = policy.get("min_page_text_chars")
        if minimum_chars is not None:
            for physical_index in range(cover_pages, page_count):
                if page_text_lengths[physical_index] < int(minimum_chars):
                    _add_finding(findings, "SPARSE_BODY_PAGE", "WARNING", f"Physical page {physical_index + 1} contains only {page_text_lengths[physical_index]} extracted text characters; inspect for under-filled layout.")

        expected_page_map = policy.get("expected_page_map", {})
        if expected_page_map:
            for heading, expected_page_number in expected_page_map.items():
                matches = []
                for physical_index in range(cover_pages, page_count):
                    if _top_heading_present(pages[physical_index], str(heading)):
                        printed = body_start_number + (physical_index - cover_pages)
                        matches.append(printed)
                if not matches:
                    _add_finding(findings, "TOC_HEADING_NOT_FOUND", "ERROR", f"Expected heading was not found in the body: {heading}.")
                elif int(expected_page_number) not in matches:
                    _add_finding(findings, "TOC_PAGE_MAP_MISMATCH", "ERROR", f"Heading '{heading}' is expected on page {expected_page_number}; detected body page(s): {matches}.")

    # Structural warning: a visible pass can still rely on a fragile zero-start trick.
    sections = docx_metrics["sections"]
    has_zero_start = any(item["start_page_number"] == 0 for item in sections)
    if cover_pages > 0 and len(sections) == 1 and has_zero_start:
        severity = "ERROR" if policy.get("require_dedicated_cover_section", False) else "WARNING"
        _add_finding(
            findings,
            "NONSTANDARD_ZERO_BASED_COVER_NUMBERING",
            severity,
            "Cover numbering is implemented through a single section with page numbering starting at zero. Prefer a dedicated unnumbered cover section followed by a body section starting at one.",
        )
    elif cover_pages > 0 and policy.get("require_dedicated_cover_section", False) and len(sections) < 2:
        _add_finding(findings, "MISSING_DEDICATED_COVER_SECTION", "ERROR", "A dedicated cover section is required by policy.")

    expected_size = policy.get("page_size")
    if expected_size:
        expected_dimensions = PAGE_SIZE_POINTS.get(str(expected_size).upper())
        if expected_dimensions is None:
            _add_finding(findings, "UNSUPPORTED_EXPECTED_PAGE_SIZE", "ERROR", f"Unsupported page_size policy: {expected_size}.")
        else:
            for section in sections:
                width, height = section["page_width_pt"], section["page_height_pt"]
                if abs(width - expected_dimensions[0]) > 3 or abs(height - expected_dimensions[1]) > 3:
                    _add_finding(findings, "PAGE_SIZE_MISMATCH", "ERROR", f"Section {section['index']} is {width:.1f} x {height:.1f} pt; expected {expected_size}.")

    expected_margins = policy.get("margins_cm")
    if isinstance(expected_margins, dict):
        for section in sections:
            for edge in ("top", "right", "bottom", "left"):
                if edge in expected_margins and abs(section["margins_cm"][edge] - float(expected_margins[edge])) > 0.08:
                    _add_finding(findings, "MARGIN_MISMATCH", "ERROR", f"Section {section['index']} {edge} margin is {section['margins_cm'][edge]} cm; expected {expected_margins[edge]} cm.")

    normal = docx_metrics["normal_style"]
    for key, report_key, code in (
        ("font_family", "font_family", "FONT_FAMILY_MISMATCH"),
        ("font_size_pt", "font_size_pt", "FONT_SIZE_MISMATCH"),
        ("line_spacing", "line_spacing", "LINE_SPACING_MISMATCH"),
    ):
        if key in policy:
            actual = normal.get(report_key)
            expected = policy[key]
            if key == "font_family":
                ok = actual == expected
            else:
                ok = actual is not None and abs(float(actual) - float(expected)) <= 0.02
            if not ok:
                _add_finding(findings, code, "ERROR", f"Normal style {key} is {actual!r}; expected {expected!r}.")

    if docx_metrics["images_missing_alt_count"]:
        _add_finding(findings, "IMAGE_ALT_TEXT_MISSING", "WARNING", f"{docx_metrics['images_missing_alt_count']} embedded image(s) lack alternative text.")

    errors = sum(1 for item in findings if item["severity"] == "ERROR")
    warnings = sum(1 for item in findings if item["severity"] == "WARNING")
    status = "FAIL" if errors else "WARN" if warnings else "PASS"
    return {
        "schema_version": "1.0.0",
        "status": status,
        "audited_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "docx": docx_metrics,
        "pdf": pdf_metrics,
        "pagination": {
            "cover_pages": cover_pages,
            "cover_footer_number_tokens": footer_tokens[:cover_pages],
            "body_start_number": body_start_number,
            "detected_body_page_numbers": detected_body_numbers,
            "body_numbering_sequence_valid": not any(item["code"] in {"COVER_PAGE_NUMBER_VISIBLE", "BODY_PAGE_NUMBER_SEQUENCE_MISMATCH"} for item in findings),
        },
        "findings": findings,
        "summary": {"error_count": errors, "warning_count": warnings, "page_count": page_count},
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Audit visual pagination and DOCX formatting metadata for a DOCX/PDF pair")
    parser.add_argument("docx", type=Path)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--policy", type=Path, help="optional JSON policy file")
    parser.add_argument("--output", type=Path, help="optional JSON report path; refuses to overwrite")
    args = parser.parse_args(argv)
    policy = json.loads(args.policy.read_text(encoding="utf-8")) if args.policy else {}
    report = audit_document_layout(args.docx, args.pdf, policy)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        if args.output.exists():
            raise FileExistsError(f"refusing to overwrite {args.output}")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())