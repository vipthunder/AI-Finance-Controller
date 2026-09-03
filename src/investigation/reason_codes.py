from __future__ import annotations

REASON_CODES = {
    "LIKELY_DUPLICATE": "Review for potential duplicate entry.",
    "VALIDATION_FAILED": "Review validation failures (e.g. amount/date bounds).",
    "NO_CANDIDATE": "No matching candidates found across sources.",
    "AMBIGUOUS": "Multiple candidates found with similar scores.",
    "LOW_CONFIDENCE": "Candidates found but confidence scores were too low."
}
