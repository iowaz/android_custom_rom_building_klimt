#!/usr/bin/env python3
"""TOOL_REVIEW.json for a verifier-only recheck (see README: 'Verifier fixes without a rebuild').

usage: KLIMT_BUILD=evox18 python3 -B tool_review.py <attempt> <recheckNN> <evidence.txt>
The reviewed checker must already be installed and registered in image-checks/IMAGE_CHECKS.json.
"""
import json, sys
from pathlib import Path

from controller import B, L, D, tooling_hashes, sha

attempt, recheck, evidence = sys.argv[1:4]
A = L / attempt
checks = json.loads((B / 'image-checks/IMAGE_CHECKS.json').read_text())
for c in checks:
    assert sha(Path(c['argv'][1])) == c['script_sha256'], c['name']
assert json.loads((A / 'build-exit.json').read_text())['exit'] == 0, 'recheck needs a successful build'
review = {
    'approved': True,
    'attempt': attempt,
    'source_snapshot_sha256': sha(A / 'prebuild.xml'),
    'tooling_sha256': tooling_hashes(),
    'image_checks': checks,
    'evidence': Path(evidence).read_text().strip(),
    'original_check_image_sha256': json.loads((A / 'BUILD_READY.json').read_text())['image_checks'][0]['script_sha256'],
}
out = D / attempt / f'TOOL_REVIEW.{recheck}.json'
out.parent.mkdir(parents=True, exist_ok=True)
with open(out, 'x') as f:
    f.write(json.dumps(review, indent=2) + '\n')
print('written', out)
