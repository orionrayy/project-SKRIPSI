"""Evidence-linked thesis document engineering (v0.6.0).

The module assembles only operator-supplied manuscript content. It does not
write thesis prose from metadata, abstracts, datasets, or model output. Every
build remains a draft pending human academic review.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .audit import append_audit_event, read_audit_events
from .statistics import StatisticalEngineError, verify_analysis_run

try:
    from docx import Document
    from docx.enum.section import WD_SECTION
    from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_TAB_ALIGNMENT, WD_TAB_LEADER
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Inches, Pt, RGBColor
except ImportError:  # pragma: no cover - covered by optional-dependency tests
    Document = None  # type: ignore[assignment]

try:
    import fitz
except ImportError:  # pragma: no cover
    fitz = None  # type: ignore[assignment]


class DocumentEngineError(ValueError):
    """Invalid document specification, evidence links, or build artifacts."""


SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
DOC_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$")
SUPPORTED_CITATION_STYLES = {"APA7", "IEEE"}
SUPPORTED_BLOCK_TYPES = {"paragraph", "bullet", "numbered", "table", "analysis_table", "figure"}
MAX_SECTIONS = 120
MAX_BLOCKS = 3000
MAX_TEXT_CHARS = 2_000_000
MAX_IMAGE_BYTES = 20 * 1024 * 1024


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_path(root: Path, supplied: str | Path, *, must_exist: bool = True) -> Path:
    root = root.expanduser().resolve(strict=True)
    raw = Path(supplied).expanduser()
    candidate = raw if raw.is_absolute() else root / raw
    lexical = Path(os.path.abspath(candidate))
    try:
        relative = lexical.relative_to(root)
    except ValueError as exc:
        raise DocumentEngineError("document paths must remain inside the private workspace") from exc
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise DocumentEngineError(f"symlinked workspace component is not permitted: {relative.as_posix()}")
    if must_exist:
        try:
            resolved = lexical.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError) as exc:
            raise DocumentEngineError(f"workspace file is missing or escaped: {relative.as_posix()}") from exc
        if not resolved.is_file():
            raise DocumentEngineError(f"expected a regular file: {relative.as_posix()}")
        return resolved
    return lexical


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DocumentEngineError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DocumentEngineError(f"JSON root must be an object: {path}")
    return value


def _atomic_json_new(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refusing to overwrite existing document artifact: {path}")
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temp, path)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def _default_spec(project_id: str, title: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "project_id": project_id,
        "document_id": "THESIS-DRAFT-001",
        "title": title,
        "language": "id-ID",
        "citation_style": "APA7",
        "institution_profile": {
            "path": None,
            "sha256": None,
            "approval_reference": None,
        },
        "output": {
            "filename": "thesis-draft.docx",
            "include_cover": True,
            "include_toc": True,
            "include_bibliography": True,
            "page_size": "A4",
            "formatting": {
                "font_family": "Times New Roman",
                "font_size_pt": 12,
                "line_spacing": 1.5,
                "first_line_indent_cm": 1.25,
                "space_after_pt": 0,
                "margins_cm": {"top": 3.0, "right": 2.5, "bottom": 2.5, "left": 3.0},
                "heading_sizes_pt": {"1": 14, "2": 12, "3": 12},
            },
        },
        "sections": [
            {
                "section_id": "BAB-I",
                "heading": "BAB I PENDAHULUAN",
                "level": 1,
                "blocks": [
                    {
                        "type": "paragraph",
                        "text": "Masukkan paragraf yang ditulis atau disetujui peneliti di sini.",
                        "claim_ids": [],
                    }
                ],
            }
        ],
    }


def create_document_scaffold(workspace: Path) -> Path:
    root = workspace.expanduser().resolve(strict=True)
    manifest = _read_json(_safe_path(root, "project.json"))
    output = _safe_path(root, "manuscript/document_specification.json", must_exist=False)
    _atomic_json_new(output, _default_spec(str(manifest.get("project_id", "")), str(manifest.get("title", ""))))
    return output


def _validate_profile(root: Path, spec: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None, list[str]]:
    profile_binding = spec.get("institution_profile")
    if not isinstance(profile_binding, dict):
        return None, None, ["institution_profile must be an object"]
    path_value = profile_binding.get("path")
    if path_value is None:
        return None, None, ["GENERIC_TEMPLATE: institutional formatting compliance is unverified"]
    errors: list[str] = []
    if not isinstance(path_value, str) or not path_value.strip():
        return None, None, ["institution profile path must be a workspace-relative string"]
    try:
        path = _safe_path(root, path_value, must_exist=True)
        raw_hash = sha256_file(path)
        expected_hash = profile_binding.get("sha256")
        if not isinstance(expected_hash, str) or not SHA256_RE.fullmatch(expected_hash) or expected_hash != raw_hash:
            errors.append("institution profile SHA-256 is missing or does not match the pinned profile")
        profile = _read_json(path)
    except (OSError, DocumentEngineError) as exc:
        return None, None, [str(exc)]
    if profile.get("review_status") != "HUMAN_REVIEWED":
        errors.append("institution profile must have review_status HUMAN_REVIEWED")
    if not isinstance(profile.get("reviewer_role"), str) or not profile["reviewer_role"].strip():
        errors.append("institution profile reviewer_role is required")
    approval_ref = profile_binding.get("approval_reference")
    if not isinstance(approval_ref, str) or not approval_ref.strip():
        errors.append("institution profile approval_reference is required")
    if profile.get("profile_id") is None or profile.get("version") is None:
        errors.append("institution profile_id and version are required")
    return profile, raw_hash, errors


def _validate_spec(root: Path, spec: dict[str, Any]) -> tuple[list[str], list[str], dict[str, Any] | None]:
    errors: list[str] = []
    warnings: list[str] = []
    if spec.get("schema_version") != "1.0.0":
        errors.append("schema_version must be 1.0.0")
    manifest = _read_json(_safe_path(root, "project.json"))
    if spec.get("project_id") != manifest.get("project_id"):
        errors.append("document specification project_id does not match project.json")
    doc_id = spec.get("document_id")
    if not isinstance(doc_id, str) or not DOC_ID_RE.fullmatch(doc_id):
        errors.append("document_id must be a safe 3-64 character identifier")
    if not isinstance(spec.get("title"), str) or not spec["title"].strip():
        errors.append("title must be a non-empty string")
    if spec.get("citation_style") not in SUPPORTED_CITATION_STYLES:
        errors.append("citation_style must be APA7 or IEEE")
    output = spec.get("output")
    if not isinstance(output, dict):
        errors.append("output must be an object")
        output = {}
    filename = output.get("filename")
    if not isinstance(filename, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,100}\.docx", filename):
        errors.append("output.filename must be a safe .docx filename")
    for flag in ("include_cover", "include_toc", "include_bibliography"):
        if not isinstance(output.get(flag), bool):
            errors.append(f"output.{flag} must be boolean")
    sections = spec.get("sections")
    if not isinstance(sections, list) or not sections or len(sections) > MAX_SECTIONS:
        errors.append(f"sections must contain 1-{MAX_SECTIONS} entries")
        sections = []
    section_ids: set[str] = set()
    heading_names: set[str] = set()
    block_count = 0
    text_total = 0
    for si, section in enumerate(sections):
        label = f"sections[{si}]"
        if not isinstance(section, dict):
            errors.append(f"{label} must be an object")
            continue
        sid, heading, level = section.get("section_id"), section.get("heading"), section.get("level")
        if not isinstance(sid, str) or not DOC_ID_RE.fullmatch(sid) or sid in section_ids:
            errors.append(f"{label}.section_id must be safe and unique")
        else:
            section_ids.add(sid)
        if not isinstance(heading, str) or not heading.strip():
            errors.append(f"{label}.heading must be non-empty")
        elif heading.strip().casefold() in heading_names:
            errors.append(f"{label}.heading must be unique for deterministic table-of-contents mapping")
        else:
            heading_names.add(heading.strip().casefold())
        if isinstance(level, bool) or level not in (1, 2, 3):
            errors.append(f"{label}.level must be 1, 2 or 3")
        blocks = section.get("blocks")
        if not isinstance(blocks, list):
            errors.append(f"{label}.blocks must be an array")
            continue
        for bi, block in enumerate(blocks):
            block_count += 1
            blabel = f"{label}.blocks[{bi}]"
            if not isinstance(block, dict):
                errors.append(f"{blabel} must be an object")
                continue
            kind = block.get("type")
            if kind not in SUPPORTED_BLOCK_TYPES:
                errors.append(f"{blabel}.type is unsupported")
                continue
            if kind in {"paragraph", "bullet", "numbered"}:
                text = block.get("text")
                if not isinstance(text, str) or not text.strip():
                    errors.append(f"{blabel}.text must be non-empty")
                else:
                    text_total += len(text)
            if kind == "table":
                headers, rows = block.get("headers"), block.get("rows")
                if not isinstance(headers, list) or not headers or any(not isinstance(x, str) for x in headers):
                    errors.append(f"{blabel}.headers must be a non-empty string array")
                if not isinstance(rows, list) or any(not isinstance(row, list) or len(row) != len(headers or []) for row in rows):
                    errors.append(f"{blabel}.rows must be arrays matching the header width")
            if kind == "analysis_table":
                if not isinstance(block.get("run_id"), str) or not DOC_ID_RE.fullmatch(block["run_id"]):
                    errors.append(f"{blabel}.run_id must be a safe analysis run ID")
                ids = block.get("variable_ids")
                if not isinstance(ids, list) or not ids or any(not isinstance(x, str) or not x for x in ids) or len(set(ids)) != len(ids):
                    errors.append(f"{blabel}.variable_ids must be a non-empty unique string array")
            if kind == "figure":
                for field in ("path", "caption", "alt_text"):
                    if not isinstance(block.get(field), str) or not block[field].strip():
                        errors.append(f"{blabel}.{field} is required")
            claim_ids = block.get("claim_ids", [])
            if not isinstance(claim_ids, list) or any(not isinstance(x, str) or not x.strip() for x in claim_ids):
                errors.append(f"{blabel}.claim_ids must be an array of non-empty strings")
    if block_count > MAX_BLOCKS:
        errors.append(f"document exceeds {MAX_BLOCKS} block safety limit")
    if text_total > MAX_TEXT_CHARS:
        errors.append(f"document text exceeds {MAX_TEXT_CHARS} character safety limit")
    formatting = output.get("formatting", {})
    if not isinstance(formatting, dict):
        errors.append("output.formatting must be an object")
    else:
        font_size = formatting.get("font_size_pt", 12)
        line_spacing = formatting.get("line_spacing", 1.5)
        if isinstance(font_size, bool) or not isinstance(font_size, (int, float)) or not 8 <= font_size <= 18:
            errors.append("font_size_pt must be between 8 and 18")
        if isinstance(line_spacing, bool) or not isinstance(line_spacing, (int, float)) or not 1 <= line_spacing <= 2.5:
            errors.append("line_spacing must be between 1 and 2.5")
        margins = formatting.get("margins_cm", {})
        if not isinstance(margins, dict):
            errors.append("margins_cm must be an object")
        else:
            for key in ("top", "right", "bottom", "left"):
                value = margins.get(key, 2.5)
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not 1 <= value <= 6:
                    errors.append(f"margin {key} must be between 1 and 6 cm")
    profile, profile_hash, profile_errors = _validate_profile(root, spec)
    if profile_errors and not (len(profile_errors) == 1 and profile_errors[0].startswith("GENERIC_TEMPLATE")):
        errors.extend(profile_errors)
    else:
        warnings.extend(profile_errors)
    if profile:
        requirements = profile.get("requirements", {})
        required_style = requirements.get("citation_style") if isinstance(requirements, dict) else None
        if isinstance(required_style, str) and required_style.strip():
            normalized_required = required_style.strip().upper().replace(" ", "").replace("-", "")
            normalized_selected = str(spec.get("citation_style", "")).upper().replace(" ", "").replace("-", "")
            aliases = {"APA7THEDITION": "APA7", "APA7": "APA7", "IEEE": "IEEE", "IEEESTYLE": "IEEE"}
            if aliases.get(normalized_required, normalized_required) != aliases.get(normalized_selected, normalized_selected):
                errors.append("document citation_style does not match the human-reviewed institution profile")
    return errors, warnings, profile


def _source_citations(root: Path, spec: dict[str, Any]) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]], list[str]]:
    register = _read_json(_safe_path(root, "sources/registry/source_register.json"))
    source_map = {item.get("source_id"): item for item in register.get("sources", []) if isinstance(item, dict)}
    links = register.get("claim_evidence_links", [])
    claim_to_sources: dict[str, list[dict[str, Any]]] = defaultdict(list)
    warnings: list[str] = []
    used_claims: set[str] = set()
    for section in spec.get("sections", []):
        for block in section.get("blocks", []) if isinstance(section, dict) else []:
            if isinstance(block, dict):
                used_claims.update(block.get("claim_ids", []) if isinstance(block.get("claim_ids"), list) else [])
    for claim_id in sorted(used_claims):
        matches = [link for link in links if isinstance(link, dict) and link.get("claim_id") == claim_id]
        accepted = []
        for link in matches:
            source = source_map.get(link.get("source_id"))
            if not source:
                continue
            if link.get("relation") == "SUPPORTS" and link.get("review_status") == "VERIFIED":
                accepted.append({"link": link, "source": source})
        if not accepted:
            raise DocumentEngineError(f"claim {claim_id} has no VERIFIED SUPPORTS link; it cannot be cited in a generated document")
        claim_to_sources[claim_id] = accepted
    used_sources: dict[str, dict[str, Any]] = {}
    for claim_items in claim_to_sources.values():
        for item in claim_items:
            src = item["source"]
            used_sources[src["source_id"]] = src
            if src.get("access_status") in {"METADATA_ONLY", "ABSTRACT_ONLY"}:
                warnings.append(f"{src['source_id']} is {src.get('access_status')}; its content scope is limited by the verified evidence link")
            if src.get("source_type") == "JOURNAL_ARTICLE":
                warnings.append(f"{src['source_id']} bibliographic metadata is abbreviated; verify journal/container, volume, issue and page range before submission")
            authors = src.get("authors", [])
            if any(isinstance(author, str) and "," not in author for author in authors):
                warnings.append(f"{src['source_id']} author-name order may be ambiguous; verify family-name order and initials for APA/IEEE reference formatting")
    style = spec.get("citation_style")
    if style == "APA7":
        incomplete = [sid for sid, src in used_sources.items() if not src.get("authors") or not isinstance(src.get("year"), int)]
        if incomplete:
            raise DocumentEngineError("APA7 citations require author names and publication year for: " + ", ".join(sorted(incomplete)))
    return used_sources, claim_to_sources, warnings


def _author_surname(value: str) -> str:
    value = " ".join(value.strip().split())
    if "," in value:
        return value.split(",", 1)[0].strip()
    tokens = value.split()
    return tokens[-1] if tokens else value


def _family_name(value: str) -> str:
    value = " ".join(value.strip().split())
    if "," in value:
        return value.split(",", 1)[0].strip()
    tokens = value.split()
    return tokens[-1] if tokens else value


def _author_apa(authors: list[str], explicit_citation_author: str | None = None) -> str:
    if isinstance(explicit_citation_author, str) and explicit_citation_author.strip():
        return explicit_citation_author.strip()
    names = [_family_name(item) for item in authors if isinstance(item, str) and item.strip()]
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} & {names[1]}"
    if len(names) >= 3:
        return f"{names[0]} et al."
    return ""


def _apa_reference_name(value: str) -> str:
    value = " ".join(value.strip().split())
    if not value:
        return ""
    if "," in value:
        family, given = value.split(",", 1)
        given_names = given.split()
    else:
        parts = value.split()
        family = parts[-1]
        given_names = parts[:-1]
    initials = " ".join((part[0].upper() + ".") for part in given_names if part)
    return f"{family.strip()}, {initials}" if initials else family.strip()


def _author_reference(authors: list[str], *, ieee: bool, explicit_reference_authors: str | None = None) -> str:
    clean = [" ".join(a.split()) for a in authors if isinstance(a, str) and a.strip()]
    if not clean:
        return ""
    if ieee:
        return ", ".join(clean[:6]) + (", et al." if len(clean) > 6 else "")
    if isinstance(explicit_reference_authors, str) and explicit_reference_authors.strip():
        return explicit_reference_authors.strip()
    formatted = [_apa_reference_name(value) for value in clean]
    if len(formatted) == 1:
        return formatted[0]
    if len(formatted) <= 20:
        return ", ".join(formatted[:-1]) + ", & " + formatted[-1]
    return ", ".join(formatted[:19]) + ", ... " + formatted[-1]


def _citation_plan(style: str, sources: dict[str, dict[str, Any]], claim_map: dict[str, list[dict[str, Any]]], appearance_claims: list[str]) -> tuple[dict[str, str], list[dict[str, Any]]]:
    appearance: list[str] = []
    source_order_by_claim: dict[str, list[str]] = {
        cid: [item["source"]["source_id"] for item in items]
        for cid, items in claim_map.items()
    }
    # IEEE numbering follows first appearance in the manuscript, never source-register order.
    for cid in appearance_claims:
        for sid in source_order_by_claim.get(cid, []):
            if sid not in appearance:
                appearance.append(sid)
    citation_text: dict[str, str] = {}
    if style == "IEEE":
        index = {sid: pos + 1 for pos, sid in enumerate(appearance)}
        for claim_id, source_ids in source_order_by_claim.items():
            citation_text[claim_id] = "[" + ", ".join(str(index[sid]) for sid in source_ids if sid in index) + "]"
        bibliography = [{"source_id": sid, "number": index[sid], "source": sources[sid]} for sid in appearance]
    else:
        # APA author-year collisions require a/b suffixes, assigned in stable title order.
        grouped: dict[tuple[str, int], list[str]] = defaultdict(list)
        for sid in appearance:
            source = sources[sid]
            key = (_author_apa(source.get("authors", []), source.get("citation_author")), source["year"])
            grouped[key].append(sid)
        suffix: dict[str, str] = {}
        for ids in grouped.values():
            if len(ids) > 1:
                ids.sort(key=lambda x: str(sources[x].get("title", "")).casefold())
                for i, sid in enumerate(ids):
                    suffix[sid] = chr(ord("a") + i)
        for claim_id, source_ids in source_order_by_claim.items():
            parts = []
            for sid in source_ids:
                src = sources[sid]
                author = _author_apa(src.get("authors", []), src.get("citation_author"))
                year = str(src["year"]) + suffix.get(sid, "")
                parts.append(f"{author}, {year}")
            citation_text[claim_id] = "(" + "; ".join(parts) + ")"
        bibliography = [{"source_id": sid, "source": sources[sid], "suffix": suffix.get(sid, "")} for sid in sorted(appearance, key=lambda x: (_author_apa(sources[x].get("authors", []), sources[x].get("citation_author")).casefold(), sources[x]["year"], sources[x].get("title", "").casefold()))]
    return citation_text, bibliography


def _set_cell_shading(cell: Any, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), fill)
    tc_pr.append(shading)


def _set_repeat_table_header(row: Any) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def _add_page_field(paragraph: Any) -> None:
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar"); begin.set(qn("w:fldCharType"), "begin")
    instruction = OxmlElement("w:instrText"); instruction.set(qn("xml:space"), "preserve"); instruction.text = " PAGE "
    separate = OxmlElement("w:fldChar"); separate.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t"); text.text = "1"
    end = OxmlElement("w:fldChar"); end.set(qn("w:fldCharType"), "end")
    for element in (begin, instruction, separate, text, end):
        run._r.append(element)


def _add_bookmark(paragraph: Any, bookmark_name: str, bookmark_id: int) -> None:
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), str(bookmark_id))
    start.set(qn("w:name"), bookmark_name)
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), str(bookmark_id))
    insert_at = 1 if len(paragraph._p) and paragraph._p[0].tag == qn("w:pPr") else 0
    paragraph._p.insert(insert_at, start)
    paragraph._p.append(end)


def _add_internal_hyperlink(paragraph: Any, text: str, anchor: str) -> None:
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("w:anchor"), anchor)
    run = OxmlElement("w:r")
    props = OxmlElement("w:rPr")
    style = OxmlElement("w:rStyle")
    style.set(qn("w:val"), "Hyperlink")
    props.append(style)
    run.append(props)
    text_element = OxmlElement("w:t")
    text_element.text = text
    run.append(text_element)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)


def _add_analysis_table(document: Any, root: Path, block: dict[str, Any], table_index: int) -> tuple[str, list[str]]:
    run_id = block["run_id"]
    report = verify_analysis_run(root, run_id)
    if report.get("status") != "PASS":
        raise DocumentEngineError(f"analysis run {run_id} failed verification: {report}")
    result_path = _safe_path(root, Path("analysis/outputs") / run_id / "results.json")
    run_path = _safe_path(root, Path("analysis/outputs") / run_id / "run.json")
    result = _read_json(result_path)
    run_record = _read_json(run_path)
    selected = set(block["variable_ids"])
    rows = [item for item in result.get("variable_results", []) if item.get("variable_id") in selected]
    if len(rows) != len(selected):
        raise DocumentEngineError(f"analysis table {run_id} references unknown variable_id(s)")
    warnings = [f"analysis run {run_id} is descriptive-only; do not infer causality or generalize beyond its design"]
    table = document.add_table(rows=1, cols=6)
    table.style = "Table Grid"
    header = table.rows[0]
    _set_repeat_table_header(header)
    for cell, value in zip(header.cells, ["Variabel", "Operasi", "N valid", "Missing", "Ringkasan", "Status"]):
        cell.text = value
        _set_cell_shading(cell, "D9EAF7")
    for item in rows:
        row = table.add_row()
        operation = item.get("operation")
        if operation == "NUMERIC_SUMMARY":
            if item.get("summary_suppressed"):
                summary = "Disembunyikan (small-cell suppression)"
            else:
                summary = "Mean={}; SD={}; Min={}; Max={}".format(
                    item.get("mean"), item.get("sample_standard_deviation"), item.get("minimum"), item.get("maximum")
                )
            n_value = item.get("n")
            missing = item.get("missing_n")
        else:
            cats = item.get("categories", [])
            summary = "; ".join(f"{c['category']}: {c['count']} ({c['percent_of_valid']:.1%})" for c in cats)
            hidden = item.get("suppressed_category_count", 0)
            if hidden:
                summary += f"; {hidden} kategori disembunyikan"
            n_value = item.get("valid_n")
            missing = item.get("missing_n")
        values = [item.get("variable_id", ""), operation, "Tersupresi" if n_value is None else str(n_value), str(missing), summary, "Terverifikasi"]
        for cell, value in zip(row.cells, values):
            cell.text = str(value)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    return f"Tabel {table_index}. Hasil analisis deskriptif (run {run_id})", [sha256_file(result_path), sha256_file(run_path)]


def _apply_formatting(document: Any, output_cfg: dict[str, Any], profile: dict[str, Any] | None) -> dict[str, Any]:
    formatting = dict(output_cfg.get("formatting", {}))
    if profile:
        required = profile.get("requirements", {})
        profile_fmt = required.get("formatting", {}) if isinstance(required, dict) else {}
        if isinstance(profile_fmt, dict):
            # Only supported, explicitly declared keys are applied; unknown guideline fields stay in the profile.
            formatting.update({k: v for k, v in profile_fmt.items() if k in {"font_family", "font_size_pt", "line_spacing", "first_line_indent_cm", "space_after_pt", "margins_cm", "heading_sizes_pt", "page_size"}})
    page_size = formatting.get("page_size", output_cfg.get("page_size", "A4"))
    section = document.sections[0]
    if page_size == "A4":
        section.page_width, section.page_height = Cm(21.0), Cm(29.7)
    elif page_size == "LETTER":
        section.page_width, section.page_height = Inches(8.5), Inches(11)
    else:
        raise DocumentEngineError("only A4 and LETTER page sizes are supported")
    margins = formatting.get("margins_cm", {})
    if not isinstance(margins, dict):
        raise DocumentEngineError("margins_cm must be an object")
    section.top_margin = Cm(float(margins.get("top", 3)))
    section.right_margin = Cm(float(margins.get("right", 2.5)))
    section.bottom_margin = Cm(float(margins.get("bottom", 2.5)))
    section.left_margin = Cm(float(margins.get("left", 3)))
    font = str(formatting.get("font_family", "Times New Roman"))
    size = float(formatting.get("font_size_pt", 12))
    line_spacing = float(formatting.get("line_spacing", 1.5))
    after = float(formatting.get("space_after_pt", 0))
    indent = float(formatting.get("first_line_indent_cm", 1.25))
    for style_name in ("Normal", "Body Text", "List Paragraph"):
        style = document.styles[style_name]
        style.font.name = font
        style.font.size = Pt(size)
        style._element.rPr.rFonts.set(qn("w:eastAsia"), font)
        style.paragraph_format.line_spacing = line_spacing
        style.paragraph_format.space_after = Pt(after)
    document.styles["Normal"].paragraph_format.first_line_indent = Cm(indent)
    heading_sizes = formatting.get("heading_sizes_pt", {"1": 14, "2": 12, "3": 12})
    for level in (1, 2, 3):
        style = document.styles[f"Heading {level}"]
        style.font.name = font
        style._element.rPr.rFonts.set(qn("w:eastAsia"), font)
        style.font.size = Pt(float(heading_sizes.get(str(level), size)))
        style.font.bold = True
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.paragraph_format.keep_with_next = True
        style.paragraph_format.first_line_indent = Cm(0)
        style.paragraph_format.space_before = Pt(12 if level == 1 else 8)
        style.paragraph_format.space_after = Pt(6)
    return {"page_size": page_size, "font_family": font, "font_size_pt": size, "line_spacing": line_spacing, "margins_cm": margins, "first_line_indent_cm": indent}


def _add_toc(document: Any, sections: list[dict[str, Any]], page_map: dict[str, int], bookmark_names: dict[str, str], max_width_inches: float) -> None:
    heading = document.add_paragraph()
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = heading.add_run("DAFTAR ISI")
    run.bold = True
    run.font.size = Pt(14)
    for sec in sections:
        level = sec["level"]
        p = document.add_paragraph()
        p.paragraph_format.left_indent = Cm((level - 1) * 0.6)
        p.paragraph_format.first_line_indent = Cm(0)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.tab_stops.add_tab_stop(Inches(max_width_inches), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
        _add_internal_hyperlink(p, sec["heading"], bookmark_names[sec["section_id"]])
        p.add_run("\t" + (str(page_map.get(sec["section_id"], "…"))))


def _build_docx_once(root: Path, spec: dict[str, Any], toc_sections: list[dict[str, Any]], sources: dict[str, dict[str, Any]], claim_map: dict[str, list[dict[str, Any]]], citation_text: dict[str, str], bibliography: list[dict[str, Any]], profile: dict[str, Any] | None, page_map: dict[str, int], target: Path) -> tuple[list[str], list[dict[str, Any]]]:
    if Document is None:
        raise DocumentEngineError("python-docx is required; install project-skripsi-engine[docx]")
    output_cfg = spec["output"]
    document = Document()
    formatting = _apply_formatting(document, output_cfg, profile)
    document.core_properties.title = spec["title"]
    document.core_properties.subject = "Draft assembled by Project-SKRIPSI; human academic review required"
    document.core_properties.author = "Project-SKRIPSI workspace"
    document.core_properties.keywords = "thesis; draft; not reviewed"
    section = document.sections[0]
    section.different_first_page_header_footer = True
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer.add_run("PROJECT-SKRIPSI | DRAFT - NOT REVIEWED | ")
    _add_page_field(footer)
    first_footer = section.first_page_footer.paragraphs[0]
    first_footer.text = ""

    if output_cfg.get("include_cover", True):
        cover = document.add_paragraph()
        cover.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cover.paragraph_format.space_before = Cm(4)
        manifest = _read_json(_safe_path(root, "project.json"))
        cover.add_run(str(manifest.get("institution", {}).get("name", "")) + "\n").bold = True
        programme = manifest.get("institution", {}).get("programme", "")
        if programme:
            cover.add_run(str(programme) + "\n")
        title_run = cover.add_run(spec["title"].upper())
        title_run.bold = True
        title_run.font.size = Pt(16)
        cover.add_run("\n\nDRAFT - NOT REVIEWED\n\n")
        cover.add_run(str(manifest.get("project_id", "")))
        document.add_page_break()

    if output_cfg.get("include_toc", True):
        max_w = max(3.5, (section.page_width - section.left_margin - section.right_margin) / 914400 - 0.2)
        _add_toc(document, toc_sections, page_map, {s["section_id"]: "sec_" + re.sub(r"[^A-Za-z0-9_]", "_", s["section_id"]) for s in toc_sections}, max_w)
        document.add_page_break()

    run_hashes: dict[str, list[str]] = {}
    warnings: list[str] = []
    citation_appearance_claims: list[str] = []
    table_num = 0
    figure_num = 0
    section_ids: dict[str, str] = {}
    for sec_index, sec in enumerate(spec["sections"]):
        if sec.get("level") == 1 and sec_index > 0:
            document.add_page_break()
        p = document.add_paragraph(style=f"Heading {sec['level']}")
        p.paragraph_format.first_line_indent = Cm(0)
        p.add_run(sec["heading"])
        bname = "sec_" + re.sub(r"[^A-Za-z0-9_]", "_", sec["section_id"])
        _add_bookmark(p, bname, sec_index + 1)
        section_ids[sec["section_id"]] = bname
        for block in sec["blocks"]:
            kind = block["type"]
            claim_ids = block.get("claim_ids", [])
            for cid in claim_ids:
                if cid not in citation_appearance_claims:
                    citation_appearance_claims.append(cid)
            if kind in {"paragraph", "bullet", "numbered"}:
                style_name = "List Bullet" if kind == "bullet" else "List Number" if kind == "numbered" else "Normal"
                para = document.add_paragraph(style=style_name)
                if kind == "paragraph":
                    para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                else:
                    para.paragraph_format.first_line_indent = Cm(0)
                para.add_run(block["text"])
                if claim_ids:
                    citations = [citation_text[cid] for cid in claim_ids]
                    # Collapse duplicate citation groups deterministically.
                    citation = " ".join(dict.fromkeys(citations))
                    para.add_run(" " + citation)
            elif kind == "table":
                table_num += 1
                caption = document.add_paragraph()
                caption.paragraph_format.first_line_indent = Cm(0)
                cap_text = block.get("caption") or f"Tabel {table_num}"
                caption.add_run(cap_text).bold = True
                if claim_ids:
                    caption.add_run(" " + " ".join(dict.fromkeys(citation_text[cid] for cid in claim_ids)))
                table = document.add_table(rows=1, cols=len(block["headers"]))
                table.style = "Table Grid"
                _set_repeat_table_header(table.rows[0])
                for cell, value in zip(table.rows[0].cells, block["headers"]):
                    cell.text = value
                    _set_cell_shading(cell, "D9EAF7")
                for values in block["rows"]:
                    cells = table.add_row().cells
                    for cell, value in zip(cells, values):
                        cell.text = str(value)
                        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            elif kind == "analysis_table":
                table_num += 1
                caption, hashes = _add_analysis_table(document, root, block, table_num)
                run_hashes[block["run_id"]] = hashes
                cap = document.add_paragraph()
                cap.paragraph_format.first_line_indent = Cm(0)
                cap.add_run(caption).bold = True
            elif kind == "figure":
                figure_num += 1
                img = _safe_path(root, block["path"], must_exist=True)
                if img.suffix.casefold() not in {".png", ".jpg", ".jpeg"} or img.stat().st_size > MAX_IMAGE_BYTES:
                    raise DocumentEngineError("figures must be PNG/JPEG and at most 20 MiB")
                picture = document.add_picture(str(img), width=Inches(5.5))
                picture._inline.docPr.set("descr", block["alt_text"])
                figure_caption = document.add_paragraph()
                figure_caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
                figure_caption.paragraph_format.first_line_indent = Cm(0)
                figure_caption.add_run(block["caption"] or f"Gambar {figure_num}").italic = True
    if output_cfg.get("include_bibliography", True) and bibliography:
        document.add_page_break()
        p = document.add_paragraph(style="Heading 1")
        p.paragraph_format.first_line_indent = Cm(0)
        p.add_run("DAFTAR PUSTAKA")
        _add_bookmark(p, "sec___BIBLIOGRAPHY__", len(spec["sections"]) + 1)
        for item in bibliography:
            src = item["source"]
            authors = src.get("authors", [])
            year = src.get("year")
            title = src.get("title", "")
            doi = src.get("doi")
            url = src.get("url")
            para = document.add_paragraph()
            para.paragraph_format.left_indent = Cm(1.27)
            para.paragraph_format.first_line_indent = Cm(-1.27)
            if spec["citation_style"] == "IEEE":
                para.add_run(f"[{item['number']}] ")
                para.add_run(_author_reference(authors, ieee=True) + ", ")
                para.add_run(f'"{title}," {year}. ')
            else:
                para.add_run(_author_reference(authors, ieee=False, explicit_reference_authors=src.get("reference_authors")) + f" ({year}{item.get('suffix', '')}). ")
                para.add_run(title + ". ")
            if doi:
                para.add_run(f"https://doi.org/{doi}")
            elif url:
                para.add_run(url)
    # Update all dynamic fields when opened in Word/LibreOffice; TOC itself is static and deterministic.
    settings = document.settings._element
    update_fields = OxmlElement("w:updateFields")
    update_fields.set(qn("w:val"), "true")
    settings.append(update_fields)
    target.parent.mkdir(parents=True, exist_ok=True)
    document.save(target)
    return warnings, [{"run_id": run_id, "result_sha256": hashes[0], "run_record_sha256": hashes[1]} for run_id, hashes in sorted(run_hashes.items())]


def _render_pdf(docx_path: Path, output_pdf: Path) -> None:
    soffice = shutil.which("libreoffice") or shutil.which("soffice")
    if not soffice:
        raise DocumentEngineError("LibreOffice is required to build a page-accurate TOC/PDF")
    if fitz is None:
        raise DocumentEngineError("PyMuPDF is required for page mapping; install project-skripsi-engine[document-qa]")
    with tempfile.TemporaryDirectory(prefix="project-skripsi-lo-") as profile_dir:
        profile_uri = Path(profile_dir).resolve().as_uri()
        cmd = [soffice, "-env:UserInstallation=" + profile_uri, "--headless", "--convert-to", "pdf", "--outdir", str(output_pdf.parent), str(docx_path)]
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        generated = output_pdf.parent / (docx_path.stem + ".pdf")
        if completed.returncode != 0 or not generated.exists() or generated.stat().st_size == 0:
            raise DocumentEngineError(f"LibreOffice PDF conversion failed: {completed.stderr[-1000:]} {completed.stdout[-1000:]}")
        if generated != output_pdf:
            os.replace(generated, output_pdf)


def _extract_heading_pages(pdf_path: Path, sections: list[dict[str, Any]]) -> dict[str, int]:
    if fitz is None:
        raise DocumentEngineError("PyMuPDF is required for page mapping")
    pdf = fitz.open(pdf_path)
    page_texts = [page.get_text("text") for page in pdf]
    result: dict[str, int] = {}
    for sec in sections:
        target = " ".join(sec["heading"].split()).casefold()
        matches = []
        for idx, text in enumerate(page_texts):
            lines = [" ".join(line.split()).casefold() for line in text.splitlines() if line.strip()]
            if target and target in lines:
                matches.append(idx + 1)
        if not matches:
            raise DocumentEngineError(f"rendered PDF does not contain section heading: {sec['heading']}")
        # The body heading follows the TOC entry; last occurrence is the body heading.
        result[sec["section_id"]] = max(matches)
    pdf.close()
    return result


def _atomic_publish(source: Path, destination: Path) -> None:
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"refusing to overwrite document output: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(destination, flags, 0o600)
    try:
        with source.open("rb") as input_stream, os.fdopen(fd, "wb") as output_stream:
            shutil.copyfileobj(input_stream, output_stream, length=1024 * 1024)
            output_stream.flush()
            os.fsync(output_stream.fileno())
    except BaseException:
        try:
            destination.unlink()
        except OSError:
            pass
        raise


def build_document(workspace: Path, specification: str | Path = "manuscript/document_specification.json") -> dict[str, Any]:
    root = workspace.expanduser().resolve(strict=True)
    spec_path = _safe_path(root, specification, must_exist=True)
    spec = _read_json(spec_path)
    errors, warnings, profile = _validate_spec(root, spec)
    if errors:
        raise DocumentEngineError("document specification invalid: " + "; ".join(errors))
    initial_spec_hash = sha256_file(spec_path)
    initial_manifest_hash = sha256_file(_safe_path(root, "project.json"))
    initial_source_hash = sha256_file(_safe_path(root, "sources/registry/source_register.json"))
    from .validation import validate_workspace
    workspace_errors, _workspace_manifest, _workspace_ledger = validate_workspace(root)
    if workspace_errors:
        raise DocumentEngineError("workspace validation failed: " + "; ".join(workspace_errors))
    sources, claim_map, citation_warnings = _source_citations(root, spec)
    warnings.extend(citation_warnings)
    # Preserve claim first-appearance order for IEEE numbering and bibliography traceability.
    appearance_claims = []
    for section in spec["sections"]:
        for block in section["blocks"]:
            for claim_id in block.get("claim_ids", []):
                if claim_id not in appearance_claims:
                    appearance_claims.append(claim_id)
    citation_text, bibliography = _citation_plan(spec["citation_style"], sources, claim_map, appearance_claims)
    toc_sections = list(spec["sections"])
    if spec["output"].get("include_bibliography", True) and bibliography:
        toc_sections.append({"section_id": "__BIBLIOGRAPHY__", "heading": "DAFTAR PUSTAKA", "level": 1})
    output_dir = _safe_path(root, "deliverables", must_exist=False)
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    output_name = spec["output"]["filename"]
    output_path = _safe_path(root, Path("deliverables") / output_name, must_exist=False)
    pdf_path = output_path.with_suffix(".pdf")
    if output_path.exists() or output_path.is_symlink() or pdf_path.exists() or pdf_path.is_symlink():
        raise FileExistsError("DOCX or PDF output already exists; build never overwrites")
    temp_dir = Path(tempfile.mkdtemp(prefix="project-skripsi-document-", dir=output_dir))
    temp_docx = temp_dir / output_name
    temp_pdf = temp_dir / (Path(output_name).stem + ".pdf")
    page_map: dict[str, int] = {}
    profile_hash = None
    if profile:
        binding = spec.get("institution_profile", {})
        profile_hash = sha256_file(_safe_path(root, binding["path"], must_exist=True))
    run_pins: list[dict[str, str]] = []
    try:
        previous: dict[str, int] | None = None
        for iteration in range(6):
            build_warnings, run_pins = _build_docx_once(
                root, spec, toc_sections, sources, claim_map, citation_text, bibliography, profile, page_map, temp_docx
            )
            warnings.extend(build_warnings)
            temp_pdf.unlink(missing_ok=True)
            _render_pdf(temp_docx, temp_pdf)
            current = _extract_heading_pages(temp_pdf, toc_sections)
            if previous == current:
                page_map = current
                break
            previous, page_map = current, current
        else:
            raise DocumentEngineError("TOC page mapping did not converge after six render passes")
        # Final rebuild with converged map, then final render and check again.
        build_warnings, run_pins = _build_docx_once(
            root, spec, toc_sections, sources, claim_map, citation_text, bibliography, profile, page_map, temp_docx
        )
        temp_pdf.unlink(missing_ok=True)
        _render_pdf(temp_docx, temp_pdf)
        final_map = _extract_heading_pages(temp_pdf, toc_sections)
        if final_map != page_map:
            raise DocumentEngineError("TOC page map changed on final render; refusing to publish inconsistent output")
        # Re-check inputs immediately before publishing.
        spec_hash = sha256_file(spec_path)
        manifest_path = _safe_path(root, "project.json")
        source_path = _safe_path(root, "sources/registry/source_register.json")
        manifest_hash, source_hash = sha256_file(manifest_path), sha256_file(source_path)
        if spec_hash != initial_spec_hash or manifest_hash != initial_manifest_hash or source_hash != initial_source_hash:
            raise DocumentEngineError("document inputs changed while the build was running")
        if profile:
            current_profile_hash = sha256_file(_safe_path(root, spec["institution_profile"]["path"], must_exist=True))
            if current_profile_hash != profile_hash:
                raise DocumentEngineError("institution profile changed during document build")
        for pin in run_pins:
            if verify_analysis_run(root, pin["run_id"]).get("status") != "PASS":
                raise DocumentEngineError(f"analysis run changed or no longer verifies: {pin['run_id']}")
        docx_hash = sha256_file(temp_docx)
        pdf_hash = sha256_file(temp_pdf)
        # Verify final files before atomically publishing both artifacts.
        with zipfile.ZipFile(temp_docx) as archive:
            bad_member = archive.testzip()
            if bad_member:
                raise DocumentEngineError(f"DOCX ZIP CRC failure in {bad_member}")
        _atomic_publish(temp_docx, output_path)
        _atomic_publish(temp_pdf, pdf_path)
        build_record = {
            "schema_version": "1.0.0", "document_id": spec["document_id"],
            "project_id": spec["project_id"], "built_at": _now(), "status": "DRAFT_NOT_REVIEWED",
            "citation_style": spec["citation_style"], "toc_page_map": page_map,
            "docx_path": output_path.relative_to(root).as_posix(), "docx_sha256": docx_hash,
            "pdf_path": pdf_path.relative_to(root).as_posix(), "pdf_sha256": pdf_hash,
            "specification_path": spec_path.relative_to(root).as_posix(), "specification_sha256": spec_hash,
            "project_manifest_sha256": manifest_hash, "source_register_sha256": source_hash,
            "institution_profile_sha256": profile_hash,
            "citations": [{"source_id": item["source_id"], "style_order": item.get("number")} for item in bibliography],
            "claim_ids": appearance_claims, "analysis_run_pins": run_pins,
            "warnings": sorted(set(warnings)), "human_review_status": "NOT_REVIEWED",
            "generator_version": __version__,
        }
        record_path = _safe_path(root, Path("manuscript/builds") / f"{spec['document_id']}.json", must_exist=False)
        _atomic_json_new(record_path, build_record)
        build_record_hash = sha256_file(record_path)
        append_audit_event(
            root / "audit" / "events.jsonl", event_type="THESIS_DOCUMENT_BUILT", object_type="thesis_document",
            object_id=spec["document_id"], summary=f"Built unreviewed DOCX/PDF draft; DOCX SHA-256 {docx_hash}; PDF SHA-256 {pdf_hash}; build record SHA-256 {build_record_hash}.",
            evidence_refs=[build_record["docx_path"], build_record["pdf_path"], record_path.relative_to(root).as_posix()],
            idempotency_key=f"thesis-document:{spec['document_id']}:{docx_hash}",
        )
        with fitz.open(temp_pdf) as final_pdf:
            page_count = len(final_pdf)
        return {"status": "BUILT_NOT_REVIEWED", "document_id": spec["document_id"], "docx_path": build_record["docx_path"], "pdf_path": build_record["pdf_path"], "docx_sha256": docx_hash, "pdf_sha256": pdf_hash, "page_count": page_count, "toc_page_map": page_map, "build_record": record_path.relative_to(root).as_posix(), "warnings": build_record["warnings"]}
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def verify_document_build(workspace: Path, document_id: str) -> dict[str, Any]:
    root = workspace.expanduser().resolve(strict=True)
    if not DOC_ID_RE.fullmatch(document_id):
        raise DocumentEngineError("document_id must be a safe identifier")
    record_path = _safe_path(root, Path("manuscript/builds") / f"{document_id}.json", must_exist=True)
    record = _read_json(record_path)
    errors: list[str] = []
    for path_key, hash_key in (("docx_path", "docx_sha256"), ("pdf_path", "pdf_sha256"), ("specification_path", "specification_sha256")):
        try:
            path = _safe_path(root, record.get(path_key, ""), must_exist=True)
            if sha256_file(path) != record.get(hash_key):
                errors.append(f"{path_key} content SHA-256 mismatch")
        except (DocumentEngineError, OSError) as exc:
            errors.append(f"{path_key}: {exc}")
    try:
        structure = audit_docx_structure(_safe_path(root, record.get("docx_path", "")))
        if structure.get("status") != "PASS":
            errors.extend(structure.get("issues", ["DOCX structural audit failed"]))
    except (DocumentEngineError, OSError) as exc:
        errors.append(f"DOCX structural audit: {exc}")
    if sha256_file(_safe_path(root, "project.json")) != record.get("project_manifest_sha256"):
        errors.append("project manifest changed since build")
    if sha256_file(_safe_path(root, "sources/registry/source_register.json")) != record.get("source_register_sha256"):
        errors.append("source register changed since build")
    if record.get("institution_profile_sha256"):
        spec = _read_json(_safe_path(root, record.get("specification_path", "")))
        profile_path = spec.get("institution_profile", {}).get("path")
        if not profile_path or sha256_file(_safe_path(root, profile_path)) != record["institution_profile_sha256"]:
            errors.append("institution profile changed since build")
    for pin in record.get("analysis_run_pins", []):
        if verify_analysis_run(root, pin["run_id"]).get("status") != "PASS":
            errors.append(f"analysis run no longer verifies: {pin['run_id']}")
        else:
            results = _safe_path(root, Path("analysis/outputs") / pin["run_id"] / "results.json")
            run_file = _safe_path(root, Path("analysis/outputs") / pin["run_id"] / "run.json")
            if sha256_file(results) != pin.get("result_sha256") or sha256_file(run_file) != pin.get("run_record_sha256"):
                errors.append(f"analysis run artifact changed: {pin['run_id']}")
    ok, reason, events = read_audit_events(root / "audit" / "events.jsonl")
    matching = [e for e in events if e.get("event_type") == "THESIS_DOCUMENT_BUILT" and e.get("object_id") == document_id]
    if not ok:
        errors.append("audit chain invalid: " + reason)
    elif len(matching) != 1:
        errors.append("exactly one thesis document build audit event is required")
    else:
        summary = matching[0].get("summary", "")
        record_hash = sha256_file(record_path)
        if record.get("docx_sha256") not in summary:
            errors.append("audit event does not pin current DOCX hash")
        if record_hash not in summary:
            errors.append("audit event does not pin current build-record hash")
    # Verify that the static TOC page mapping still points to the headings in the retained PDF.
    if fitz is not None and isinstance(record.get("toc_page_map"), dict):
        try:
            pdf = fitz.open(_safe_path(root, record.get("pdf_path", "")))
            for heading_id, page_number in record["toc_page_map"].items():
                if isinstance(page_number, bool) or not isinstance(page_number, int) or not 1 <= page_number <= len(pdf):
                    errors.append(f"TOC page number is out of range for {heading_id}")
                    continue
                text = " ".join(pdf[page_number - 1].get_text("text").split()).casefold()
                if heading_id == "__BIBLIOGRAPHY__":
                    expected = "daftar pustaka"
                else:
                    try:
                        spec_doc = _read_json(_safe_path(root, record.get("specification_path", "")))
                        expected = next(s["heading"] for s in spec_doc["sections"] if s["section_id"] == heading_id).casefold()
                    except (StopIteration, KeyError, TypeError):
                        errors.append(f"TOC page map references unknown section {heading_id}")
                        continue
                if expected not in text:
                    errors.append(f"TOC page map does not resolve to heading {heading_id}")
            pdf.close()
        except (OSError, DocumentEngineError, RuntimeError) as exc:
            errors.append(f"PDF page-map verification failed: {exc}")
    return {"status": "PASS" if not errors else "FAIL", "document_id": document_id, "errors": errors, "human_review_status": record.get("human_review_status"), "build_record_sha256": sha256_file(record_path)}


def audit_docx_structure(path: Path) -> dict[str, Any]:
    if Document is None:
        raise DocumentEngineError("python-docx is required; install project-skripsi-engine[docx]")
    path = path.expanduser().resolve(strict=True)
    if not path.is_file() or path.suffix.casefold() != ".docx":
        raise DocumentEngineError("input must be an existing .docx file")
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        names = set(archive.namelist())
        if bad:
            raise DocumentEngineError(f"DOCX ZIP CRC failure: {bad}")
        if "word/document.xml" not in names or "[Content_Types].xml" not in names:
            raise DocumentEngineError("DOCX package is missing mandatory OOXML parts")
        from xml.etree import ElementTree as ET
        xml_root = ET.fromstring(archive.read("word/document.xml"))
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main", "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"}
        hyperlinks = len(xml_root.findall(".//w:hyperlink", ns))
        bookmarks = len(xml_root.findall(".//w:bookmarkStart", ns))
        image_nodes = xml_root.findall(".//wp:docPr", ns)
        images_missing_alt = [node.get("id") for node in image_nodes if not (node.get("descr") or "").strip()]
    document = Document(path)
    paragraphs = document.paragraphs
    headings = [p.text for p in paragraphs if p.style and p.style.name.startswith("Heading")]
    tables = len(document.tables)
    images = sum(1 for rel in document.part.rels.values() if "image" in rel.reltype)
    issues = []
    if images_missing_alt:
        issues.append("one or more embedded figures lack alternative text")
    if bookmarks < len(headings):
        issues.append("heading bookmarks are incomplete")
    return {"status": "PASS" if not issues else "WARN", "issues": issues, "paragraph_count": len(paragraphs), "heading_count": len(headings), "table_count": tables, "image_relationship_count": images, "image_nodes": len(image_nodes), "images_missing_alt": images_missing_alt, "hyperlink_count": hyperlinks, "bookmark_count": bookmarks, "headings": headings, "zip_crc": "PASS"}
