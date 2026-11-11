"""Original evidence-aware academic rhetoric patterns and claim-strength guardrails."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WritingPattern:
    pattern_id: str
    stage: str
    purpose: str
    evidence_level: str
    max_claim_strength: str
    template_id_text: str
    template_en_text: str
    caution: str


PATTERNS: tuple[WritingPattern, ...] = (
    WritingPattern("PS-WR-001", "introduction", "define_problem", "contextual", "bounded", "Dalam konteks [setting], [problem] tampak pada [evidence], sehingga penelitian ini berfokus pada [scope].", "In [setting], [problem] is reflected in [evidence]; this study therefore focuses on [scope].", "Replace placeholders only with verified context and local evidence."),
    WritingPattern("PS-WR-002", "literature_review", "compare_findings", "convergent", "bounded", "Sejumlah penelitian melaporkan [shared finding], sementara perbedaan pada [population/method/context] membatasi keterbandingan hasilnya.", "Several studies report [shared finding], while differences in [population/method/context] limit direct comparison.", "Do not imply consensus from one source or from inaccessible full texts."),
    WritingPattern("PS-WR-003", "literature_review", "identify_gap", "convergent", "bounded", "Pada sumber yang ditelaah, aspek [specific aspect] belum dibahas secara memadai dalam konteks [bounded context].", "Within the sources reviewed, [specific aspect] has not been adequately addressed in [bounded context].", "A research gap is bounded to the search strategy and corpus actually reviewed."),
    WritingPattern("PS-WR-004", "results", "report_association", "observational", "bounded", "Hasil menunjukkan adanya hubungan antara [variable A] dan [variable B] pada [population/context] dalam data yang dianalisis.", "The analyzed data show an association between [variable A] and [variable B] in [population/context].", "Association is not causation; state the design and uncertainty."),
    WritingPattern("PS-WR-005", "discussion", "interpret_limited_result", "observational", "tentative", "Temuan ini dapat mengindikasikan [interpretation], tetapi penjelasan tersebut perlu dibaca dengan mempertimbangkan [limitation].", "This finding may indicate [interpretation], although that explanation should be considered alongside [limitation].", "Interpretation must not exceed the measured variables or design."),
    WritingPattern("PS-WR-006", "discussion", "contrast_evidence", "convergent", "bounded", "Temuan ini berbeda dari [source/case] pada [dimension]; perbedaan tersebut mungkin berkaitan dengan [documented contextual difference].", "This finding differs from [source/case] in [dimension]; the difference may relate to [documented contextual difference].", "Only name a contextual explanation when the source supports it."),
    WritingPattern("PS-WR-007", "limitations", "state_limitation", "contextual", "bounded", "Hasil penelitian perlu ditafsirkan dengan memperhatikan [specific limitation], yang membatasi [scope of inference].", "The findings should be interpreted in light of [specific limitation], which constrains [scope of inference].", "Name the actual limitation and explain which inference it constrains."),
    WritingPattern("PS-WR-008", "conclusion", "bounded_conclusion", "direct", "bounded", "Dalam batas [population/time/design], penelitian ini menemukan [direct result] untuk menjawab [research question].", "Within the limits of [population/time/design], this study found [direct result] in response to [research question].", "Conclusions must map to reported results, not expected outcomes."),
    WritingPattern("PS-WR-009", "recommendation", "propose_next_step", "contextual", "tentative", "Penelitian berikutnya dapat menguji [specific unresolved issue] dengan [method/data] untuk menilai apakah temuan ini berlaku pada [new scope].", "Future research could examine [specific unresolved issue] using [method/data] to assess whether the finding extends to [new scope].", "Recommendations are proposals, not claims that an intervention will work."),
)

_EVIDENCE_RANK = {"none": 0, "contextual": 1, "observational": 2, "direct": 3, "convergent": 4}
_STRENGTH_RANK = {"tentative": 0, "bounded": 1, "assertive": 2, "causal": 3}


def list_patterns(stage: str | None = None) -> list[dict[str, str]]:
    selected = [item for item in PATTERNS if stage is None or item.stage == stage]
    return [
        {
            "pattern_id": item.pattern_id,
            "stage": item.stage,
            "purpose": item.purpose,
            "evidence_level": item.evidence_level,
            "max_claim_strength": item.max_claim_strength,
            "template_id_text": item.template_id_text,
            "template_en_text": item.template_en_text,
            "caution": item.caution,
        }
        for item in selected
    ]


def assess_claim_strength(
    *,
    evidence_level: str,
    requested_strength: str,
    research_design: str,
    causal_identification_reviewed: bool = False,
    human_reviewer_role: str | None = None,
) -> dict[str, Any]:
    """Flag overclaiming; never automatically authorize causal language."""
    if evidence_level not in _EVIDENCE_RANK:
        raise ValueError(f"unsupported evidence_level: {evidence_level}")
    if requested_strength not in _STRENGTH_RANK:
        raise ValueError(f"unsupported requested_strength: {requested_strength}")
    findings: list[str] = []
    status = "NEEDS_HUMAN_REVIEW"
    max_strength = "bounded" if evidence_level in {"contextual", "observational", "convergent"} else "assertive"
    if evidence_level == "none":
        max_strength = "tentative"
        findings.append("No claim-supporting evidence was supplied.")
    if requested_strength == "causal":
        if research_design not in {"QUANTITATIVE_EXPERIMENT", "QUASI_EXPERIMENTAL", "CAUSAL_INFERENCE"}:
            findings.append("Causal wording is incompatible with the declared non-causal design.")
        if not causal_identification_reviewed:
            findings.append("Causal identification assumptions have not been reviewed.")
        if not human_reviewer_role:
            findings.append("A qualified human reviewer role is required for causal-claim review.")
        findings.append("The engine never grants causal approval; inspect design, assumptions and alternative explanations.")
        status = "HIGH_RISK_REVIEW_REQUIRED"
    elif _STRENGTH_RANK[requested_strength] > _STRENGTH_RANK[max_strength]:
        findings.append(f"Requested claim strength exceeds the default ceiling for {evidence_level} evidence.")
        status = "OVERCLAIM_RISK"
    elif findings:
        status = "REVIEW_REQUIRED"
    return {
        "status": status,
        "evidence_level": evidence_level,
        "requested_strength": requested_strength,
        "default_ceiling": max_strength,
        "research_design": research_design,
        "causal_identification_reviewed": causal_identification_reviewed,
        "human_reviewer_role": human_reviewer_role,
        "findings": findings,
        "automatically_approved": False,
    }
