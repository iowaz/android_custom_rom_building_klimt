"""Apply narrow audit updates after callers bind a verifier review to source and tooling."""
import json


def apply(original, review, load_record, validate_candidate):
    ready = json.loads(json.dumps(original))
    if 'image_checks' in review:
        ready['image_checks'] = review['image_checks']
    if 'kernel_audit_update' in review:
        if not ready.get('candidate_evidence'):
            raise ValueError('A kernel audit update requires the original candidate admission')
        previous = ready['candidate_evidence']['kernel_audit']
        if review.get('kernel_audit_previous_sha256') != previous['sha256']:
            raise ValueError('Kernel audit update does not bind the original evidence')
        old = load_record(previous)
        new = load_record(review['kernel_audit_update'])
        if new['source_heads'] != old['source_heads'] or new['baseline_manifest_sha256'] != old['baseline_manifest_sha256']:
            raise ValueError('Verifier recheck cannot change kernel inputs or control')
        ready['candidate_evidence']['kernel_audit'] = review['kernel_audit_update']
        validate_candidate(ready, ready['reviewed_project_heads'])
    ready['verification_only'] = True
    return ready
