"""Local-only parsing and comparison of exported Turnitin Similarity Reports.

The parser reads report metadata, top-source labels, and visible numeric source
badges on thesis pages. It does not read or persist thesis paragraph text, infer
plagiarism, estimate AI-writing probability, or predict a future similarity score.
PyMuPDF is optional and must be installed via the ``pdf-qa`` extra.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


class TurnitinReportError(ValueError):
    """Raised when a PDF is not a supported exported Turnitin report."""


_ID_RE = re.compile(r"^\d{1,3}$")
_PERCENT_RE = re.compile(r"^(?:<\s*1|\d{1,3})(?:\.\d+)?%$")
_REPORT_PAGE_RE = re.compile(r"Page\s+(\d+)\s+of\s+(\d+)\s+-\s+(.+)", re.I)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pdf_text_pages(path: Path):
    try:
        import fitz  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise TurnitinReportError("PyMuPDF is required; install project-skripsi-engine[pdf-qa]") from exc
    if not path.is_file():
        raise TurnitinReportError(f"PDF not found: {path}")
    try:
        document = fitz.open(path)
    except Exception as exc:
        raise TurnitinReportError(f"cannot open PDF: {exc}") from exc
    if not len(document):
        document.close()
        raise TurnitinReportError("PDF contains no pages")
    return document


def _normalise_exclusion(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def _parse_top_sources(pages: list[str]) -> list[dict[str, Any]]:
    """Parse numbered source entries from the report's top-source pages."""
    lines: list[str] = []
    collecting = False
    for text in pages:
        split = [line.strip() for line in text.splitlines() if line.strip()]
        if not collecting:
            for i, line in enumerate(split):
                if "The sources with the highest number of matches" in line:
                    collecting = True
                    lines.extend(split[i + 1:])
                    break
        else:
            lines.extend(split)
    records: list[dict[str, Any]] = []
    i = 0
    while i < len(lines):
        if not _ID_RE.fullmatch(lines[i]):
            i += 1
            continue
        source_id = int(lines[i])
        if i + 1 >= len(lines):
            break
        source_type = lines[i + 1]
        if source_type.casefold() not in {"internet", "publication", "student papers"}:
            i += 1
            continue
        label_lines: list[str] = []
        similarity_label = None
        j = i + 2
        while j < len(lines):
            current = lines[j]
            # A following numbered source begins a new record only after the
            # current label has already obtained a similarity token.
            if _PERCENT_RE.fullmatch(current):
                similarity_label = current.replace(" ", "")
                j += 1
                break
            label_lines.append(current)
            j += 1
            if j < len(lines) and _ID_RE.fullmatch(lines[j]) and j + 1 < len(lines) and lines[j + 1].casefold() in {"internet", "publication", "student papers"}:
                break
        label = re.sub(r"\s+", " ", " ".join(label_lines)).strip()
        if label:
            records.append({
                "source_id": source_id,
                "source_type": source_type.upper().replace(" ", "_"),
                "source_label": label,
                "reported_match_share": similarity_label,
            })
        i = max(j, i + 1)
    # Preserve first occurrence while avoiding duplicate page-footer text.
    unique: dict[int, dict[str, Any]] = {}
    for record in records:
        unique.setdefault(record["source_id"], record)
    return [unique[key] for key in sorted(unique)]


def _page_label(text: str) -> tuple[int | None, int | None, str | None]:
    for line in text.splitlines():
        match = _REPORT_PAGE_RE.search(line.strip())
        if match:
            return int(match.group(1)), int(match.group(2)), match.group(3).strip()
    return None, None, None


def _extract_source_badges(document, first_body_index: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Read only visible numeric source badges drawn at the left of body pages."""
    occurrences: list[dict[str, Any]] = []
    skipped_shapes = 0
    for page_index in range(first_body_index, len(document)):
        page = document[page_index]
        words = page.get_text("words")
        for drawing in page.get_drawings():
            rect = drawing.get("rect")
            if rect is None:
                continue
            # Turnitin's rendered source badge is a small colored pill at x~7 pt.
            if not (rect.x0 <= 11.5 and 14 <= rect.width <= 22 and 11 <= rect.height <= 20 and 18 <= rect.y0 <= page.rect.height - 18):
                continue
            candidates = []
            for word in words:
                x0, y0, x1, y1, token = word[:5]
                if not str(token).isdigit():
                    continue
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                if rect.x0 - 3 <= cx <= rect.x1 + 3 and rect.y0 - 3 <= cy <= rect.y1 + 3:
                    candidates.append((abs(cx - (rect.x0 + rect.x1) / 2), int(token)))
            if not candidates:
                skipped_shapes += 1
                continue
            _, source_id = sorted(candidates)[0]
            occurrences.append({"pdf_page": page_index + 1, "source_id": source_id})
    summary = {
        "source_badge_occurrences": len(occurrences),
        "unique_source_ids": len({item["source_id"] for item in occurrences}),
        "pages_with_source_badges": len({item["pdf_page"] for item in occurrences}),
        "unreadable_badge_shapes": skipped_shapes,
    }
    return occurrences, summary


def audit_turnitin_report(pdf_path: Path | str) -> dict[str, Any]:
    """Extract an auditable, content-minimised Turnitin report inventory."""
    path = Path(pdf_path).expanduser().resolve()
    document = _pdf_text_pages(path)
    try:
        page_texts = [page.get_text("text") for page in document]
        first_text = page_texts[0]
        second_text = page_texts[1] if len(page_texts) > 1 else ""
        complete_text = "\n".join(page_texts[: min(15, len(page_texts))])

        submission_match = re.search(r"Submission\s*ID\s*(trn:oid:::[\w:-]+|[\w:-]+)", first_text, re.I)
        filename_match = re.search(r"File\s*Name\s*\n\s*(.+)", first_text, re.I)
        date_match = re.search(r"Submission\s*Date\s*\n\s*(.+)", first_text, re.I)
        words_match = re.search(r"([\d,]+)\s+Words", first_text, re.I)
        chars_match = re.search(r"([\d,]+)\s+Characters", first_text, re.I)
        file_size_match = re.search(r"File\s*Size\s*\n\s*(.+)", first_text, re.I)
        page_count_match = re.search(r"(\d+)\s+Pages", first_text, re.I)
        similarity_match = re.search(r"(\d{1,3})%\s*Overall Similarity", second_text, re.I)
        if not similarity_match:
            raise TurnitinReportError("Turnitin Overall Similarity value not found on Integrity Overview page")

        exclusions: list[str] = []
        exclusion_match = re.search(r"Filtered\s+from\s+the\s+Report(.*?)(?:Top\s+Sources|$)", second_text, re.I | re.S)
        if exclusion_match:
            for line in exclusion_match.group(1).splitlines():
                label = line.strip(" \t•-–")
                if label and not re.fullmatch(r"[\d.%]+", label):
                    exclusions.append(label)

        category_patterns = {
            "internet_sources": r"(\d{1,3})%\s*Internet sources",
            "publications": r"(\d{1,3})%\s*Publications",
            "student_papers": r"(\d{1,3})%\s*Submitted works\s*\(Student Papers\)",
        }
        categories = {}
        for key, pattern in category_patterns.items():
            found = re.search(pattern, second_text, re.I)
            categories[key] = int(found.group(1)) if found else None

        overview_pages: list[int] = []
        first_body_index = None
        total_pages_from_label = None
        for index, text in enumerate(page_texts):
            shown, total, label = _page_label(text)
            if total and total_pages_from_label is None:
                total_pages_from_label = total
            if label and "Integrity Submission" in label:
                first_body_index = index if first_body_index is None else first_body_index
            elif label and "Integrity Overview" in label and shown and shown >= 3:
                overview_pages.append(index)
        if first_body_index is None:
            # Fallback: first page containing an Integrity Submission footer.
            for index, text in enumerate(page_texts):
                if re.search(r"Page\s+\d+\s+of\s+\d+\s+-\s+Integrity Submission", text, re.I):
                    first_body_index = index
                    break
        if first_body_index is None:
            raise TurnitinReportError("cannot determine beginning of thesis pages in Turnitin report")

        source_pages = [page_texts[index] for index in overview_pages]
        sources = _parse_top_sources(source_pages)
        badge_occurrences, badge_summary = _extract_source_badges(document, first_body_index)
        known_ids = {source["source_id"] for source in sources}
        out_of_range = sorted({entry["source_id"] for entry in badge_occurrences} - known_ids)

        submission_date = date_match.group(1).strip() if date_match else None
        page_count = int(page_count_match.group(1)) if page_count_match else len(document) - first_body_index
        result = {
            "schema_version": "1.0.0",
            "audit_type": "TURNITIN_EXPORTED_REPORT",
            "status": "PASS" if not out_of_range and sources else "CONDITIONAL",
            "report": {
                "submission_id": submission_match.group(1) if submission_match else None,
                "submission_date_text": submission_date,
                "file_name": filename_match.group(1).strip() if filename_match else None,
                "pdf_sha256": _sha256(path),
                "pdf_bytes": path.stat().st_size,
                "pdf_page_count": len(document),
                "thesis_page_count_reported": page_count,
                "thesis_first_pdf_page": first_body_index + 1,
                "word_count_reported": int(words_match.group(1).replace(",", "")) if words_match else None,
                "character_count_reported": int(chars_match.group(1).replace(",", "")) if chars_match else None,
                "original_docx_file_size_text": file_size_match.group(1).strip() if file_size_match else None,
                "overall_similarity_percent": int(similarity_match.group(1)),
                "visible_exclusions": exclusions,
                "source_category_percentages": categories,
            },
            "source_inventory": {
                "source_entries_parsed": len(sources),
                "source_types": dict(Counter(item["source_type"] for item in sources)),
                "sources": sources,
            },
            "body_source_badges": {
                **badge_summary,
                "out_of_range_source_ids": out_of_range,
                "occurrences": badge_occurrences,
                "interpretation": "Visible source-badge occurrences, not unique matched words or unique passages.",
            },
            "text_storage": "REPORT_METADATA_ONLY_NO_THESIS_BODY_TEXT_STORED",
            "similarity_interpretation": "A matching-text indicator; not an automated plagiarism verdict, authorship judgment, or AI-writing probability.",
            "limitations": [
                "PDF export may omit account-side settings not printed in the report.",
                "Top-source entries are limited to sources rendered in the report export.",
                "Visible source-badge counts are drawing-level counts and do not measure matched-word volume.",
                "Source labels are not a substitute for opening and evaluating the underlying sources.",
            ],
        }
        return result
    finally:
        document.close()


def compare_turnitin_reports(baseline_pdf: Path | str, current_pdf: Path | str) -> dict[str, Any]:
    """Compare visible metadata from two reports without predicting causation."""
    baseline = audit_turnitin_report(baseline_pdf)
    current = audit_turnitin_report(current_pdf)
    old = baseline["report"]
    new = current["report"]
    old_exclusions = sorted(_normalise_exclusion(item) for item in old["visible_exclusions"])
    new_exclusions = sorted(_normalise_exclusion(item) for item in new["visible_exclusions"])
    same_exclusions = old_exclusions == new_exclusions
    old_score = old["overall_similarity_percent"]
    new_score = new["overall_similarity_percent"]
    category_deltas = {}
    for key, old_value in old["source_category_percentages"].items():
        new_value = new["source_category_percentages"].get(key)
        category_deltas[key] = (new_value - old_value) if isinstance(old_value, int) and isinstance(new_value, int) else None
    return {
        "schema_version": "1.0.0",
        "audit_type": "TURNITIN_REPORT_COMPARISON",
        "status": "COMPARABLE_VISIBLE_SETTINGS" if same_exclusions else "CONDITIONAL_SETTINGS_DIFFER",
        "baseline": {
            "submission_id": old.get("submission_id"),
            "submission_date_text": old.get("submission_date_text"),
            "pdf_sha256": old["pdf_sha256"],
            "overall_similarity_percent": old_score,
            "visible_exclusions": old["visible_exclusions"],
            "thesis_page_count_reported": old["thesis_page_count_reported"],
            "word_count_reported": old["word_count_reported"],
            "source_category_percentages": old["source_category_percentages"],
        },
        "current": {
            "submission_id": new.get("submission_id"),
            "submission_date_text": new.get("submission_date_text"),
            "pdf_sha256": new["pdf_sha256"],
            "overall_similarity_percent": new_score,
            "visible_exclusions": new["visible_exclusions"],
            "thesis_page_count_reported": new["thesis_page_count_reported"],
            "word_count_reported": new["word_count_reported"],
            "source_category_percentages": new["source_category_percentages"],
        },
        "change": {
            "overall_similarity_percentage_point_delta": new_score - old_score,
            "relative_change_percent": round((new_score - old_score) / old_score * 100, 4) if old_score else None,
            "source_category_percentage_point_deltas": category_deltas,
            "top_source_entry_count_delta": current["source_inventory"]["source_entries_parsed"] - baseline["source_inventory"]["source_entries_parsed"],
            "source_badge_occurrence_delta": current["body_source_badges"]["source_badge_occurrences"] - baseline["body_source_badges"]["source_badge_occurrences"],
            "unique_source_badge_id_delta": current["body_source_badges"]["unique_source_ids"] - baseline["body_source_badges"]["unique_source_ids"],
            "word_count_delta": (new["word_count_reported"] - old["word_count_reported"]) if isinstance(new["word_count_reported"], int) and isinstance(old["word_count_reported"], int) else None,
            "thesis_page_count_delta": (new["thesis_page_count_reported"] - old["thesis_page_count_reported"]) if isinstance(new["thesis_page_count_reported"], int) and isinstance(old["thesis_page_count_reported"], int) else None,
            "visible_exclusions_match": same_exclusions,
        },
        "comparability": {
            "visible_exclusion_settings_match": same_exclusions,
            "same_reported_thesis_page_count": old["thesis_page_count_reported"] == new["thesis_page_count_reported"],
            "same_reported_file_name": old.get("file_name") == new.get("file_name"),
            "database_and_account_side_settings_verified": False,
            "assessment": "The exported reports can be compared on their visible settings, but identical Turnitin database/account configuration is not provable from the PDFs alone.",
        },
        "no_plagiarism_verdict": True,
        "no_ai_detector_prediction": True,
        "notice": "A score change is a descriptive difference between two exported reports; it does not establish authorship, originality, plagiarism, or why the score changed.",
    }
