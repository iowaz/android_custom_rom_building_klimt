"""Bind ordinary promotions and explicit verifier-only rechecks to their own tooling."""
import json


def validate(attempt_id, recheck, staged, attempt, require_frozen, review_binding, sha):
    if recheck:
        review = json.loads((staged/'TOOL_REVIEW.json').read_text())
        review_binding(review, attempt_id, sha(attempt/'prebuild.xml'))
    else:
        require_frozen(attempt)
