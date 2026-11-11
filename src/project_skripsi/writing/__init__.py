"""Academic-writing assistance with evidence and authorship safeguards."""

from .patterns import assess_claim_strength, list_patterns
from .revision import LocalOpenAICompatibleClient, audit_revision, build_revision_prompt

__all__ = [
    "LocalOpenAICompatibleClient",
    "assess_claim_strength",
    "audit_revision",
    "build_revision_prompt",
    "list_patterns",
]
