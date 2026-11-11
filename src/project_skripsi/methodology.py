"""Deterministic checks for research-design alignment.

The engine flags traceability gaps and review risks. It does not select a design,
statistical test, sample size, instrument, or claim that a method is valid.
"""
from __future__ import annotations

from typing import Any

VALID_DESIGNS = {
    "QUANTITATIVE_SURVEY", "QUANTITATIVE_EXPERIMENT", "QUALITATIVE",
    "MIXED_METHODS", "SECONDARY_DATA", "CASE_STUDY", "SYSTEMATIC_REVIEW", "OTHER",
}
VALID_INTENTS = {"DESCRIPTIVE", "EXPLORATORY", "RELATIONAL", "COMPARATIVE", "CAUSAL", "EVALUATIVE", "INTERPRETIVE"}
VALID_STRATEGIES = {
    "DESCRIPTIVE", "INFERENTIAL", "QUALITATIVE_CODING", "THEMATIC_ANALYSIS",
    "CONTENT_ANALYSIS", "DOCUMENT_ANALYSIS", "COMPARATIVE", "OTHER",
}
VALID_CONSTRUCT_ROLES = {
    "EXPLANATORY", "PREDICTOR", "INDEPENDENT", "OUTCOME", "DEPENDENT",
    "MEDIATOR", "MODERATOR", "CONTROL", "QUALITATIVE_CONCEPT", "MIXED_METHODS_COMPONENT",
}
VALID_MEASUREMENT_LEVELS = {"NOMINAL", "ORDINAL", "INTERVAL", "RATIO", "CATEGORICAL", "TEXTUAL", "NOT_APPLICABLE"}
VALID_DIRECTIONS = {"POSITIVE", "NEGATIVE", "DIFFERENCE", "NON_DIRECTIONAL", "OTHER"}
VALID_INTEGRATION_STAGES = {"DESIGN", "DATA_COLLECTION", "ANALYSIS", "INTERPRETATION", "REPORTING"}


def _text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    cleaned = value.strip().casefold()
    return bool(cleaned) and cleaned not in {"tbd", "todo", "n/a?", "belum ditentukan", "belum ada", "?"}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _add(findings: list[dict[str, str]], code: str, severity: str, path: str, message: str) -> None:
    findings.append({"code": code, "severity": severity, "path": path, "message": message})


def _index_records(
    records: list[Any], *, collection: str, id_field: str, findings: list[dict[str, str]],
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(records):
        path = f"{collection}[{index}]"
        if not isinstance(record, dict):
            _add(findings, "RECORD_NOT_OBJECT", "ERROR", path, "Setiap elemen harus berupa object.")
            continue
        item_id = record.get(id_field)
        if not isinstance(item_id, str) or not item_id.strip():
            _add(findings, "ID_REQUIRED", "ERROR", f"{path}.{id_field}", "ID unik dan non-empty wajib diisi.")
            continue
        item_id = item_id.strip()
        if item_id in indexed:
            _add(findings, "DUPLICATE_ID", "ERROR", f"{path}.{id_field}", f"ID {item_id!r} duplikat dalam {collection}.")
            continue
        indexed[item_id] = record
    return indexed


def _check_refs(
    records: list[Any], *, collection: str, field: str, allowed: set[str], findings: list[dict[str, str]],
    required: bool = False,
) -> None:
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        refs = record.get(field)
        path = f"{collection}[{index}].{field}"
        if refs is None and not required:
            continue
        if not isinstance(refs, list) or (required and not refs):
            _add(findings, "REFERENCES_REQUIRED", "ERROR", path, "Minimal satu referensi ID wajib diisi.")
            continue
        if any(not isinstance(ref, str) or not ref.strip() for ref in refs):
            _add(findings, "REFERENCE_INVALID", "ERROR", path, "Referensi harus berupa array ID non-empty.")
            continue
        for ref in refs:
            if ref not in allowed:
                _add(findings, "REFERENCE_UNKNOWN", "ERROR", path, f"Referensi {ref!r} tidak ditemukan pada registry terkait.")


def audit_research_alignment(
    document: dict[str, Any],
    methodology_profile: dict[str, Any] | None = None,
    source_register: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Audit links between questions, objectives, constructs, hypotheses and analysis.

    A clear result means only that the supplied structure is internally traceable.
    It is never an academic approval or statistical-method recommendation.
    """
    findings: list[dict[str, str]] = []
    if not isinstance(document, dict):
        _add(findings, "DOCUMENT_NOT_OBJECT", "ERROR", "$", "Dokumen alignment harus berupa object JSON.")
        return _result(None, findings)

    if document.get("schema_version") != "1.0.0":
        _add(findings, "SCHEMA_VERSION_UNSUPPORTED", "ERROR", "schema_version", "schema_version alignment harus 1.0.0.")

    project_id = document.get("project_id")
    if not isinstance(project_id, str) or len(project_id.strip()) < 3:
        _add(findings, "PROJECT_ID_REQUIRED", "ERROR", "project_id", "project_id minimal tiga karakter.")

    raw_design = document.get("research_design")
    if not isinstance(raw_design, str) or raw_design not in VALID_DESIGNS:
        _add(findings, "DESIGN_UNSUPPORTED", "ERROR", "research_design", "research_design tidak termasuk enum yang didukung.")
        design = None
    else:
        design = raw_design

    questions_raw = _items(document.get("research_questions"))
    objectives_raw = _items(document.get("objectives"))
    constructs_raw = _items(document.get("constructs"))
    hypotheses_raw = _items(document.get("hypotheses"))
    analyses_raw = _items(document.get("analysis_plan"))
    integrations_raw = _items(document.get("integration_points"))

    if not questions_raw:
        _add(findings, "QUESTIONS_REQUIRED", "ERROR", "research_questions", "Tambahkan minimal satu pertanyaan penelitian yang sudah dirumuskan peneliti.")
    if not objectives_raw:
        _add(findings, "OBJECTIVES_REQUIRED", "ERROR", "objectives", "Tambahkan minimal satu tujuan penelitian.")
    if not analyses_raw:
        _add(findings, "ANALYSIS_PLAN_REQUIRED", "ERROR", "analysis_plan", "Setiap pertanyaan penelitian harus memiliki rencana analisis yang dipilih dan dijustifikasi peneliti.")
    if design in {"QUANTITATIVE_SURVEY", "QUANTITATIVE_EXPERIMENT", "SECONDARY_DATA"} and not constructs_raw:
        _add(findings, "QUANTITATIVE_CONSTRUCTS_REVIEW", "WARNING", "constructs", "Daftar variabel/konstruk belum diisi; tentukan berdasarkan pertanyaan dan sumber data, bukan inferensi otomatis.")

    questions = _index_records(questions_raw, collection="research_questions", id_field="question_id", findings=findings)
    objectives = _index_records(objectives_raw, collection="objectives", id_field="objective_id", findings=findings)
    constructs = _index_records(constructs_raw, collection="constructs", id_field="construct_id", findings=findings)
    hypotheses = _index_records(hypotheses_raw, collection="hypotheses", id_field="hypothesis_id", findings=findings)
    analyses = _index_records(analyses_raw, collection="analysis_plan", id_field="analysis_id", findings=findings)

    for item_id, question in questions.items():
        if not _text(question.get("text")):
            _add(findings, "QUESTION_TEXT_REQUIRED", "ERROR", f"research_questions.{item_id}.text", "Teks pertanyaan penelitian wajib diisi.")
        intent = question.get("intent")
        if not isinstance(intent, str) or intent not in VALID_INTENTS:
            _add(findings, "QUESTION_INTENT_UNSUPPORTED", "ERROR", f"research_questions.{item_id}.intent", "Pilih intent yang menjelaskan bentuk pertanyaan, bukan metode analisis.")
        if intent == "CAUSAL" and design in {"QUANTITATIVE_SURVEY", "SECONDARY_DATA", "CASE_STUDY"}:
            _add(findings, "CAUSAL_INFERENCE_REVIEW_REQUIRED", "WARNING", f"research_questions.{item_id}", "Pertanyaan kausal pada desain yang belum menunjukkan identifikasi kausal memerlukan justifikasi desain, temporalitas, confounding, dan strategi identifikasi oleh reviewer.")

    _check_refs(objectives_raw, collection="objectives", field="research_question_ids", allowed=set(questions), findings=findings, required=True)
    for objective_id, objective in objectives.items():
        if not _text(objective.get("text")):
            _add(findings, "OBJECTIVE_TEXT_REQUIRED", "ERROR", f"objectives.{objective_id}.text", "Pernyataan tujuan penelitian wajib diisi.")
    for question_id in questions:
        if not any(isinstance(obj, dict) and question_id in _items(obj.get("research_question_ids")) for obj in objectives_raw):
            _add(findings, "QUESTION_WITHOUT_OBJECTIVE", "WARNING", f"research_questions.{question_id}", "Belum ada tujuan penelitian yang dipetakan ke pertanyaan ini.")

    for construct_id, construct in constructs.items():
        raw_role = construct.get("role")
        if not isinstance(raw_role, str) or raw_role not in VALID_CONSTRUCT_ROLES:
            _add(findings, "CONSTRUCT_ROLE_UNSUPPORTED", "ERROR", f"constructs.{construct_id}.role", "Peran konstruk/variabel tidak dikenal.")
            role = None
        else:
            role = raw_role
        if not _text(construct.get("name")):
            _add(findings, "CONSTRUCT_NAME_REQUIRED", "ERROR", f"constructs.{construct_id}.name", "Nama konstruk/variabel wajib diisi.")
        level = construct.get("measurement_level")
        if level is not None and (not isinstance(level, str) or level not in VALID_MEASUREMENT_LEVELS):
            _add(findings, "MEASUREMENT_LEVEL_UNSUPPORTED", "ERROR", f"constructs.{construct_id}.measurement_level", "Measurement level tidak dikenal.")
        if design in {"QUANTITATIVE_SURVEY", "QUANTITATIVE_EXPERIMENT", "SECONDARY_DATA"} and role not in {"QUALITATIVE_CONCEPT", "MIXED_METHODS_COMPONENT"}:
            if level is None:
                _add(findings, "MEASUREMENT_LEVEL_MISSING", "WARNING", f"constructs.{construct_id}.measurement_level", "Tentukan tingkat pengukuran berdasarkan definisi operasional dan instrumen; sistem tidak menentukannya otomatis.")
            if not _text(construct.get("operationalization")):
                _add(findings, "OPERATIONALIZATION_MISSING", "WARNING", f"constructs.{construct_id}.operationalization", "Definisi operasional belum terdokumentasi.")
            indicators = construct.get("indicators", [])
            if not isinstance(indicators, list) or not indicators or any(not _text(x) for x in indicators):
                _add(findings, "INDICATORS_MISSING", "WARNING", f"constructs.{construct_id}.indicators", "Indikator/item pengukuran belum dijelaskan; reviewer harus menilai kesesuaian konstruk dan instrumen.")

    _check_refs(hypotheses_raw, collection="hypotheses", field="research_question_ids", allowed=set(questions), findings=findings, required=True)
    _check_refs(hypotheses_raw, collection="hypotheses", field="predictor_construct_ids", allowed=set(constructs), findings=findings, required=True)
    _check_refs(hypotheses_raw, collection="hypotheses", field="outcome_construct_ids", allowed=set(constructs), findings=findings, required=True)
    for hypothesis_id, hypothesis in hypotheses.items():
        if not _text(hypothesis.get("text")):
            _add(findings, "HYPOTHESIS_TEXT_REQUIRED", "ERROR", f"hypotheses.{hypothesis_id}.text", "Pernyataan hipotesis wajib diisi.")
        direction = hypothesis.get("direction")
        if not isinstance(direction, str) or direction not in VALID_DIRECTIONS:
            _add(findings, "HYPOTHESIS_DIRECTION_UNSUPPORTED", "ERROR", f"hypotheses.{hypothesis_id}.direction", "Arah hubungan harus dipilih atau dinyatakan OTHER.")
        for predictor_id in _items(hypothesis.get("predictor_construct_ids")):
            if not isinstance(predictor_id, str):
                continue
            predictor = constructs.get(predictor_id)
            predictor_role = predictor.get("role") if predictor else None
            if predictor and (not isinstance(predictor_role, str) or predictor_role not in {"EXPLANATORY", "PREDICTOR", "INDEPENDENT", "MEDIATOR", "MODERATOR", "CONTROL"}):
                _add(findings, "HYPOTHESIS_PREDICTOR_ROLE_REVIEW", "WARNING", f"hypotheses.{hypothesis_id}.predictor_construct_ids", f"Konstruk {predictor_id!r} berperan {predictor_role!r}, bukan peran predictor yang lazim; periksa pemodelan konseptual.")
        for outcome_id in _items(hypothesis.get("outcome_construct_ids")):
            if not isinstance(outcome_id, str):
                continue
            outcome = constructs.get(outcome_id)
            outcome_role = outcome.get("role") if outcome else None
            if outcome and (not isinstance(outcome_role, str) or outcome_role not in {"OUTCOME", "DEPENDENT"}):
                _add(findings, "HYPOTHESIS_OUTCOME_ROLE_REVIEW", "WARNING", f"hypotheses.{hypothesis_id}.outcome_construct_ids", f"Konstruk {outcome_id!r} bukan berperan OUTCOME/DEPENDENT; periksa pemodelan konseptual.")
        if design == "QUALITATIVE":
            _add(findings, "HYPOTHESIS_IN_QUALITATIVE_DESIGN_REVIEW", "WARNING", f"hypotheses.{hypothesis_id}", "Pastikan hipotesis memang sesuai paradigma dan desain kualitatif yang dipilih; hipotesis tidak diwajibkan untuk semua penelitian kualitatif.")

    _check_refs(analyses_raw, collection="analysis_plan", field="research_question_ids", allowed=set(questions), findings=findings, required=True)
    _check_refs(analyses_raw, collection="analysis_plan", field="hypothesis_ids", allowed=set(hypotheses), findings=findings)
    _check_refs(analyses_raw, collection="analysis_plan", field="construct_ids", allowed=set(constructs), findings=findings)

    question_analysis_map: dict[str, list[dict[str, Any]]] = {qid: [] for qid in questions}
    hypothesis_analysis_map: dict[str, list[dict[str, Any]]] = {hid: [] for hid in hypotheses}
    for analysis_id, analysis in analyses.items():
        if not _text(analysis.get("technique")):
            _add(findings, "ANALYSIS_TECHNIQUE_REQUIRED", "ERROR", f"analysis_plan.{analysis_id}.technique", "Tuliskan teknik analisis yang dipilih peneliti.")
        if not _text(analysis.get("selection_rationale")):
            _add(findings, "ANALYSIS_RATIONALE_REQUIRED", "ERROR", f"analysis_plan.{analysis_id}.selection_rationale", "Jelaskan mengapa teknik tersebut sesuai dengan pertanyaan, jenis data, unit analisis, dan desain.")
        raw_strategy = analysis.get("strategy")
        if not isinstance(raw_strategy, str) or raw_strategy not in VALID_STRATEGIES:
            _add(findings, "ANALYSIS_STRATEGY_UNSUPPORTED", "ERROR", f"analysis_plan.{analysis_id}.strategy", "Kategori strategi analisis tidak dikenal.")
            strategy = None
        else:
            strategy = raw_strategy
        diagnostics = analysis.get("assumption_diagnostics", [])
        if not isinstance(diagnostics, list) or any(not _text(item) for item in diagnostics):
            _add(findings, "DIAGNOSTICS_FORMAT_INVALID", "ERROR", f"analysis_plan.{analysis_id}.assumption_diagnostics", "assumption_diagnostics harus berupa array string non-empty; gunakan array kosong bila tidak relevan dan jelaskan alasannya di rationale.")
        if strategy == "INFERENTIAL" and isinstance(diagnostics, list) and not diagnostics:
            _add(findings, "INFERENTIAL_DIAGNOSTICS_REVIEW", "WARNING", f"analysis_plan.{analysis_id}.assumption_diagnostics", "Rencana inferensial belum mendokumentasikan asumsi/diagnostik yang akan diperiksa.")
        if design == "QUALITATIVE" and strategy in {"DESCRIPTIVE", "INFERENTIAL"}:
            _add(findings, "STRATEGY_DESIGN_REVIEW", "WARNING", f"analysis_plan.{analysis_id}.strategy", "Strategi kuantitatif pada desain QUALITATIVE memerlukan penjelasan integrasi atau koreksi klasifikasi desain.")
        if design in {"QUANTITATIVE_SURVEY", "QUANTITATIVE_EXPERIMENT"} and strategy in {"QUALITATIVE_CODING", "THEMATIC_ANALYSIS", "CONTENT_ANALYSIS", "DOCUMENT_ANALYSIS"}:
            _add(findings, "STRATEGY_DESIGN_REVIEW", "WARNING", f"analysis_plan.{analysis_id}.strategy", "Strategi kualitatif pada desain kuantitatif memerlukan penjelasan komponen atau koreksi klasifikasi desain.")
        for qid in _items(analysis.get("research_question_ids")):
            if isinstance(qid, str) and qid in question_analysis_map:
                question_analysis_map[qid].append(analysis)
        for hid in _items(analysis.get("hypothesis_ids")):
            if isinstance(hid, str) and hid in hypothesis_analysis_map:
                hypothesis_analysis_map[hid].append(analysis)
                linked_qids = {ref for ref in _items(analysis.get("research_question_ids")) if isinstance(ref, str)}
                hypothesis_qids = {ref for ref in _items(hypotheses[hid].get("research_question_ids")) if isinstance(ref, str)}
                if not hypothesis_qids.issubset(linked_qids):
                    _add(findings, "HYPOTHESIS_QUESTION_ANALYSIS_MISMATCH", "ERROR", f"analysis_plan.{analysis_id}.hypothesis_ids", f"Rencana analisis {analysis_id!r} tidak mencakup seluruh pertanyaan yang terkait dengan hipotesis {hid!r}.")

    for qid, mapped in question_analysis_map.items():
        if not mapped:
            _add(findings, "QUESTION_WITHOUT_ANALYSIS", "ERROR", f"research_questions.{qid}", "Tidak ditemukan rencana analisis yang terhubung ke pertanyaan ini.")

    for hid, mapped in hypothesis_analysis_map.items():
        if not mapped:
            _add(findings, "HYPOTHESIS_WITHOUT_ANALYSIS", "WARNING", f"hypotheses.{hid}", "Hipotesis belum dipetakan ke rencana analisis.")
            continue
        hypothesis = hypotheses[hid]
        required_constructs = {
            ref for ref in _items(hypothesis.get("predictor_construct_ids")) + _items(hypothesis.get("outcome_construct_ids"))
            if isinstance(ref, str)
        }
        mapped_constructs: set[str] = set()
        for analysis in mapped:
            mapped_constructs.update(ref for ref in _items(analysis.get("construct_ids")) if isinstance(ref, str))
        if not required_constructs.issubset(mapped_constructs):
            _add(findings, "HYPOTHESIS_CONSTRUCTS_NOT_IN_ANALYSIS", "ERROR", f"hypotheses.{hid}", "Rencana analisis belum mencakup semua konstruk predictor dan outcome dari hipotesis.")

    if design == "MIXED_METHODS":
        if not integrations_raw:
            _add(findings, "MIXED_INTEGRATION_REQUIRED", "ERROR", "integration_points", "Mixed-methods memerlukan titik integrasi eksplisit, bukan sekadar dua jenis data.")
        analysis_ids = set(analyses)
        seen_integration_ids: set[str] = set()
        quantitative_strategies = {"DESCRIPTIVE", "INFERENTIAL", "COMPARATIVE"}
        qualitative_strategies = {"QUALITATIVE_CODING", "THEMATIC_ANALYSIS", "CONTENT_ANALYSIS", "DOCUMENT_ANALYSIS"}
        for index, point in enumerate(integrations_raw):
            path = f"integration_points[{index}]"
            if not isinstance(point, dict):
                _add(findings, "INTEGRATION_NOT_OBJECT", "ERROR", path, "Titik integrasi harus berupa object.")
                continue
            integration_id = point.get("integration_id")
            if not _text(integration_id):
                _add(findings, "INTEGRATION_ID_REQUIRED", "ERROR", f"{path}.integration_id", "integration_id wajib diisi.")
            elif integration_id in seen_integration_ids:
                _add(findings, "DUPLICATE_INTEGRATION_ID", "ERROR", f"{path}.integration_id", f"integration_id {integration_id!r} duplikat.")
            else:
                seen_integration_ids.add(integration_id)
            stage = point.get("stage")
            if not isinstance(stage, str) or stage not in VALID_INTEGRATION_STAGES:
                _add(findings, "INTEGRATION_STAGE_UNSUPPORTED", "ERROR", f"{path}.stage", "Tahap integrasi tidak dikenal.")
            quant_ids = point.get("quant_analysis_ids", [])
            qual_ids = point.get("qual_analysis_ids", [])
            refs_well_formed = (
                isinstance(quant_ids, list) and isinstance(qual_ids, list)
                and bool(quant_ids) and bool(qual_ids)
                and all(isinstance(ref, str) and ref for ref in quant_ids + qual_ids)
            )
            if not refs_well_formed:
                _add(findings, "INTEGRATION_STRANDS_REQUIRED", "ERROR", path, "Setiap titik integrasi harus merujuk minimal satu analysis_id string untuk strand kuantitatif dan satu untuk strand kualitatif.")
            else:
                if len(quant_ids) != len(set(quant_ids)) or len(qual_ids) != len(set(qual_ids)):
                    _add(findings, "INTEGRATION_DUPLICATE_ANALYSIS_REF", "ERROR", path, "Rujukan analysis_id dalam setiap strand harus unik.")
                if set(quant_ids) & set(qual_ids):
                    _add(findings, "INTEGRATION_STRANDS_OVERLAP", "ERROR", path, "Satu analysis_id tidak boleh dicantumkan sekaligus sebagai strand kuantitatif dan kualitatif.")
                for ref in quant_ids + qual_ids:
                    if ref not in analysis_ids:
                        _add(findings, "INTEGRATION_ANALYSIS_UNKNOWN", "ERROR", path, f"Rujukan analisis {ref!r} tidak ditemukan.")
                for ref in quant_ids:
                    analysis = analyses.get(ref)
                    analysis_strategy = analysis.get("strategy") if analysis else None
                    if isinstance(analysis_strategy, str) and analysis_strategy in qualitative_strategies:
                        _add(findings, "INTEGRATION_STRAND_STRATEGY_MISMATCH", "ERROR", f"{path}.quant_analysis_ids", f"Analisis {ref!r} memakai strategi kualitatif tetapi dicantumkan pada strand kuantitatif.")
                    elif analysis and analysis_strategy not in quantitative_strategies:
                        _add(findings, "INTEGRATION_STRAND_STRATEGY_REVIEW", "WARNING", f"{path}.quant_analysis_ids", f"Strategi analisis {ref!r} ambigu untuk strand kuantitatif; konfirmasi klasifikasi dengan peneliti.")
                for ref in qual_ids:
                    analysis = analyses.get(ref)
                    analysis_strategy = analysis.get("strategy") if analysis else None
                    if isinstance(analysis_strategy, str) and analysis_strategy in quantitative_strategies:
                        _add(findings, "INTEGRATION_STRAND_STRATEGY_MISMATCH", "ERROR", f"{path}.qual_analysis_ids", f"Analisis {ref!r} memakai strategi kuantitatif tetapi dicantumkan pada strand kualitatif.")
                    elif analysis and analysis_strategy not in qualitative_strategies:
                        _add(findings, "INTEGRATION_STRAND_STRATEGY_REVIEW", "WARNING", f"{path}.qual_analysis_ids", f"Strategi analisis {ref!r} ambigu untuk strand kualitatif; konfirmasi klasifikasi dengan peneliti.")
            if not _text(point.get("integration_rationale")):
                _add(findings, "INTEGRATION_RATIONALE_REQUIRED", "ERROR", f"{path}.integration_rationale", "Jelaskan fungsi integrasi dan bagaimana satu strand berhubungan dengan strand lain.")

    if source_register is not None:
        if not isinstance(source_register, dict):
            _add(findings, "SOURCE_REGISTER_NOT_OBJECT", "ERROR", "source_register", "Source register harus berupa object.")
        else:
            if source_register.get("project_id") != project_id:
                _add(findings, "SOURCE_REGISTER_PROJECT_MISMATCH", "ERROR", "source_register.project_id", "Source register dan research alignment harus memiliki project_id yang sama.")
            source_rows = source_register.get("sources")
            if not isinstance(source_rows, list):
                _add(findings, "SOURCE_REGISTER_ROWS_INVALID", "ERROR", "source_register.sources", "Source register harus memiliki array sources.")
                source_map: dict[str, dict[str, Any]] = {}
            else:
                source_map = {}
                for index, source in enumerate(source_rows):
                    path = f"source_register.sources[{index}]"
                    if not isinstance(source, dict):
                        _add(findings, "SOURCE_RECORD_NOT_OBJECT", "ERROR", path, "Source record harus berupa object.")
                        continue
                    source_id = source.get("source_id")
                    if not isinstance(source_id, str) or not source_id.strip():
                        _add(findings, "SOURCE_ID_REQUIRED", "ERROR", f"{path}.source_id", "Setiap source record harus memiliki source_id.")
                    elif source_id in source_map:
                        _add(findings, "SOURCE_ID_DUPLICATE", "ERROR", f"{path}.source_id", f"source_id {source_id!r} duplikat.")
                    else:
                        source_map[source_id] = source
            reference_groups = []
            for construct_id, construct in constructs.items():
                reference_groups.append((f"constructs.{construct_id}.source_or_instrument_refs", construct.get("source_or_instrument_refs", [])))
            for hypothesis_id, hypothesis in hypotheses.items():
                reference_groups.append((f"hypotheses.{hypothesis_id}.theoretical_basis_source_ids", hypothesis.get("theoretical_basis_source_ids", [])))
            for path, refs in reference_groups:
                if not isinstance(refs, list) or any(not isinstance(ref, str) or not ref for ref in refs):
                    _add(findings, "SOURCE_REFERENCES_INVALID", "ERROR", path, "Referensi sumber harus berupa array source_id string non-empty.")
                    continue
                for source_id in refs:
                    source = source_map.get(source_id)
                    if source is None:
                        _add(findings, "SOURCE_REFERENCE_UNKNOWN", "ERROR", path, f"Source ID {source_id!r} tidak ditemukan dalam source register proyek.")
                        continue
                    access_status = source.get("access_status")
                    if access_status in {"METADATA_ONLY", "ABSTRACT_ONLY", "NOT_ACCESSIBLE", "RESTRICTED_UNAVAILABLE"}:
                        _add(findings, "SOURCE_SCOPE_LIMITED_REVIEW_REQUIRED", "WARNING", path, f"Source {source_id!r} berstatus {access_status}; detail teori, konstruk atau instrumen belum tentu dapat didukung dari akses tersebut.")

    if methodology_profile is not None:
        if not isinstance(methodology_profile, dict):
            _add(findings, "PROFILE_NOT_OBJECT", "ERROR", "methodology_profile", "Methodology profile harus berupa object.")
        else:
            if document.get("project_id") != methodology_profile.get("project_id"):
                _add(findings, "PROJECT_ID_MISMATCH", "ERROR", "project_id", "project_id alignment dan methodology profile berbeda.")
            if design != methodology_profile.get("research_design"):
                _add(findings, "DESIGN_MISMATCH", "ERROR", "research_design", "research_design alignment dan methodology profile berbeda.")
            profile_qids = methodology_profile.get("research_question_ids", [])
            if not isinstance(profile_qids, list) or any(not isinstance(qid, str) for qid in profile_qids):
                _add(findings, "PROFILE_QUESTION_IDS_INVALID", "ERROR", "methodology_profile.research_question_ids", "Daftar ID pertanyaan pada methodology profile harus berupa array string.")
            elif set(profile_qids) != set(questions):
                _add(findings, "QUESTION_REGISTER_MISMATCH", "ERROR", "research_questions", "ID pertanyaan pada alignment harus sama dengan methodology_profile.research_question_ids.")

    return _result(design, findings, project_id=project_id if isinstance(project_id, str) else None)


def _result(design: Any, findings: list[dict[str, str]], *, project_id: str | None = None) -> dict[str, Any]:
    error_count = sum(1 for item in findings if item["severity"] == "ERROR")
    warning_count = sum(1 for item in findings if item["severity"] == "WARNING")
    review_count = sum(1 for item in findings if item["severity"] == "REVIEW")
    return {
        "schema_version": "1.0.0",
        "project_id": project_id,
        "research_design": design,
        "status": "NEEDS_REVISION" if error_count else "READY_FOR_HUMAN_REVIEW",
        "human_approval": "NOT_GRANTED",
        "summary": {"errors": error_count, "warnings": warning_count, "review_items": review_count, "findings": len(findings)},
        "findings": findings,
        "notice": "Struktural alignment PASS tidak membuktikan validitas teori, instrumen, sampling, estimasi statistik, atau inferensi kausal. Tidak ada metode/uji statistik yang dipilih otomatis; persetujuan akademik tetap memerlukan peninjau manusia.",
    }
