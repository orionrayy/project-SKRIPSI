"""Stable lifecycle contracts for an individual thesis workspace."""

THESIS_PHASES = (
    ("T0", "Intake & Project Charter"),
    ("T1", "Research Question & Proposal Design"),
    ("T2", "Literature Review & Conceptual Framework"),
    ("T3", "Methodology & Instrument Design"),
    ("T4", "Ethics, Permissions & Data Readiness"),
    ("T5", "Data Collection & Provenance"),
    ("T6", "Data Preparation & Analysis"),
    ("T7", "Results, Discussion & Interpretation"),
    ("T8", "Manuscript, Compliance & Revision"),
    ("T9", "Final Review, Defense & Publication Readiness"),
)

EXECUTION_STATUSES = {"NOT_STARTED", "IN_PROGRESS", "BLOCKED", "COMPLETE"}
VALIDATION_STATUSES = {"NOT_RUN", "PASS", "PASS_WITH_LIMITATION", "FAIL"}
ACCEPTANCE_STATUSES = {"PENDING", "ACCEPTED", "ACCEPTED_WITH_CONDITIONS", "REJECTED", "DEFERRED"}
APPROVAL_STATUSES = {"PENDING", "APPROVED", "REJECTED", "NOT_REQUIRED"}
AUTHORIZATION_STATUSES = {"NOT_AUTHORIZED", "AUTHORIZED_SCOPED", "APPROVED_SCOPED", "REVOKED"}
COMPLETE_CONCLUSION = "COMPLETE_AND_APPROVED"
