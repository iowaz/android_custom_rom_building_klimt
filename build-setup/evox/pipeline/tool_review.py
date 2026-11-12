#!/usr/bin/env python3
"""TOOL_REVIEW.json for a verifier-only recheck (see README: 'Verifier fixes without a rebuild').

usage: KLIMT_BUILD=20261105 python3 -B tool_review.py <attempt> <recheckNN> <evidence.txt>
         [--kernel-audit /absolute/revalidated-audit.json] [--mode full] [--extra NAME ...]
The reviewed checker must already be installed and registered in image-checks/IMAGE_CHECKS.json.
--mode/--extra widen the sealed verification record (more checks, never fewer); omitted, the recheck inherits it.
"""
import hostcheck
hostcheck.require_linux(__file__)
import argparse, json
from pathlib import Path

from controller import B, L, D, tooling_hashes, sha
import verification

ap = argparse.ArgumentParser()
ap.add_argument('attempt')
ap.add_argument('recheck')
ap.add_argument('evidence')
ap.add_argument('--kernel-audit')
ap.add_argument('--mode', choices=verification.MODES)
ap.add_argument('--extra', action='append', default=[], choices=verification.EXTRAS)
args = ap.parse_args()
A = L / args.attempt
checks = json.loads((B / 'image-checks/IMAGE_CHECKS.json').read_text())
for c in checks:
    assert sha(Path(c['argv'][1])) == c['script_sha256'], c['name']
assert json.loads((A / 'build-exit.json').read_text())['exit'] == 0, 'recheck needs a successful build'
original = json.loads((A / 'BUILD_READY.json').read_text())
review = {
    'approved': True,
    'attempt': args.attempt,
    'source_snapshot_sha256': sha(A / 'prebuild.xml'),
    'tooling_sha256': tooling_hashes(),
    'image_checks': checks,
    'evidence': Path(args.evidence).read_text().strip(),
    'original_check_image_sha256': original['image_checks'][0]['script_sha256'],
}
if args.mode or args.extra:
    sealed = original.get('verification')
    if sealed is None and args.mode != 'full':
        raise SystemExit('A readiness without a verification record is verified in full; only --mode full applies')
    if sealed is None or args.mode == 'full':
        wanted = dict(schema=verification.SCHEMA, mode='full', extras=[], candidate=bool(original.get('candidate_evidence')),
                      baseline=(sealed or {}).get('baseline'))
    else:
        wanted = dict(sealed, extras=sorted(set(sealed['extras']) | set(args.extra)))
    wanted['reasons'] = list((sealed or {}).get('reasons', [])) + ['recheck ' + args.recheck + ': ' + review['evidence'][:200]]
    wanted['request'] = dict(mode=args.mode, extras=sorted(args.extra), reason='tool review ' + args.recheck)
    review['verification_original_sha256'] = sha(A / 'BUILD_READY.json')
    review['verification'] = verification.widen(sealed, wanted)
if args.kernel_audit:
    import candidate_gates, reviewed_readiness
    review['kernel_audit_previous_sha256'] = original['candidate_evidence']['kernel_audit']['sha256']
    review['kernel_audit_update'] = candidate_gates.file_record(args.kernel_audit)
    reviewed_readiness.apply(original, review, candidate_gates.revalidate, candidate_gates.validate_ready)
out = D / args.attempt / f'TOOL_REVIEW.{args.recheck}.json'
out.parent.mkdir(parents=True, exist_ok=True)
with open(out, 'x') as f:
    f.write(json.dumps(review, indent=2) + '\n')
print('written', out)
