"""TOOL_REVIEW.json for a verifier-only recheck of an evox17 attempt (README 'recheck' contract).

usage: make_tool_review17.py <attempt> <recheckNN> <evidence.txt>
The reviewed checker must already be installed in the evox17 tooling directory.
"""
from pathlib import Path
import json, sys
sys.path.insert(0, '/mnt/c/XiaomiBuilds/build-setup/evox/evox17')
from controller import B, L, D, tooling_hashes, sha  # noqa: E402

attempt, recheck, evidence = sys.argv[1:4]
A = L / attempt
checks = json.loads((B / 'image-checks/IMAGE_CHECKS.json').read_text())
for c in checks:
    assert sha(Path(c['argv'][1])) == c['script_sha256'], c['name']
exit_record = json.loads((A / 'build-exit.json').read_text())
assert exit_record['exit'] == 0, 'recheck needs a successful build'
original = json.loads((A / 'BUILD_READY.json').read_text())['image_checks'][0]['script_sha256']
review = {
    'approved': True,
    'attempt': attempt,
    'source_snapshot_sha256': sha(A / 'prebuild.xml'),
    'tooling_sha256': tooling_hashes(),
    'image_checks': checks,
    'evidence': Path(evidence).read_text().strip(),
    'original_check_image_sha256': original,
    'reviewer': 'Claude, with the independent Codex evox17 review (codex-review-evox17/EVOX17_FINDINGS.json)',
}
out = D / attempt / f'TOOL_REVIEW.{recheck}.json'
with open(out, 'x') as f:
    f.write(json.dumps(review, indent=2) + '\n')
print('written', out, 'check_image', checks[0]['script_sha256'])
