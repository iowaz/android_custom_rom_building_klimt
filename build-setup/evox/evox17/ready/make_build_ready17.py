"""Issue BUILD_READY.json for the evox17 updatepackage attempt. Fails closed on any unmet gate."""
from pathlib import Path
import json, subprocess as sp, sys

sys.path.insert(0, '/mnt/c/XiaomiBuilds/build-setup/evox/evox17')
from controller import B, manifest_heads, live_heads, check_capacity, sha  # noqa: E402

S = Path('/mnt/wsl/evox/src'); R = Path('/mnt/c/XiaomiBuilds/debug/evox17'); H = Path(__file__).resolve().parent
final = json.loads((R / 'FINAL_SOURCE.json').read_text()); heads = final['heads']
assert sha(Path(final['snapshot'])) == final['snapshot_sha256'] and manifest_heads(Path(final['snapshot']).read_bytes()) == heads
live_heads(heads)
checks = []
def check(name, condition, evidence):
    if not condition:
        raise SystemExit('GATE NOT MET: ' + name + ' :: ' + evidence)
    checks.append({'name': name, 'pass': True, 'evidence': evidence})

check('frozen full graph, clean worktrees', final['pass'] and final['all_worktrees_clean'] and final['projects'] == 1263,
      f"{R / 'FINAL_SOURCE.json'}: {final['projects']} projects, snapshot {final['snapshot_sha256']}, manifest commit {final['manifest_repository_commit']}")
changes = json.loads((R / 'FROZEN_CHANGES.json').read_text())
pins = {'device/xiaomi/klimt', 'build/soong', 'frameworks/native', 'hardware/interfaces', 'hardware/xiaomi'}
check('every other GitHub project at its upstream branch head (make-frozen.py)', all(heads[c['path']] == c['new'] for c in changes),
      f"{R / 'FROZEN_CHANGES.json'}: {sum(c['old'] != c['new'] for c in changes)} revisions moved from evox16-frozen; reviewed pins {sorted(pins)} plus kernel/vendor/MediaTek policy")
apply = sp.run(['python3', str(S / 'device/xiaomi/klimt/patches/tree/apply.py'), str(S)], capture_output=True, text=True)
check('device patch bundle is exactly the two carried evox15 changes, already final',
      apply.returncode == 0 and apply.stdout.split('\n')[:2] == ['Equivalent full final tree; skip build/soong', 'Equivalent full final tree; skip frameworks/native'],
      'patches/tree/apply.py on the frozen tree: ' + apply.stdout.strip().replace('\n', '; '))
review = H / 'codex-review/EVOX16_INDEPENDENT_REVIEW.md'; verdicts = json.loads((H / 'codex-review/EVOX16_VERDICTS.json').read_text())
disp = json.loads((H / 'EVOX16_REVIEW_DISPOSITION.json').read_text())
check('evox16 self review and independent Codex review merged', review.is_file() and verdicts['changes'] and len(disp['changes']) >= 19,
      f"{review} ({len(verdicts['changes'])} verdicts); disposition {H / 'EVOX16_REVIEW_DISPOSITION.json'}")
neg = json.loads((R / 'install-integrity-negative-evox16/staged-not-installed.json').read_text())
check('install_integrity rejects the evox16 boot-loop image', 'system/priv-app/Telecom/Telecom.apk' in neg['other'],
      f"{R / 'install-integrity-negative-evox16'}: strays {neg['other']}")
build = (B / 'build.sh').read_text()
check('build wrapper cleans staging before updatepackage', build.index('m -j12 installclean') < build.index('m -j12 updatepackage') and 'STAGING_NOT_CLEAN' in build,
      str(B / 'build.sh'))
sem = json.loads((H / 'semantic_checks.json').read_text())
check('five semantic source purposes bound to frozen heads', len(sem) == 5 and all(s['pass'] and s['head'] == heads[s['project']] for s in sem),
      str(H / 'semantic_checks.json'))
image_checks = json.loads((B / 'image-checks/IMAGE_CHECKS.json').read_text())
for c in image_checks:
    assert sha(Path(c['argv'][1])) == c['script_sha256'], c['name']
tests = json.loads((B / 'image-checks/TEST_RESULTS.linux.json').read_text())
check('seven image checks registered and self-tested on Linux',
      len(image_checks) == 7 and tests['passed'] and tests['skipped'] == 0 and tests['check_image_py_sha256'] == image_checks[0]['script_sha256'],
      f"{B / 'image-checks/IMAGE_CHECKS.json'} (sha {image_checks[0]['script_sha256'][:12]}); {tests['tests_run']} Linux tests pass")

ready = {
    'approved': True, 'runtime_unvalidated': True, 'target': 'lineage_klimt-cp2a-user',
    'snapshot': final['snapshot'], 'sha256': final['snapshot_sha256'],
    'reviewed_project_heads': heads, 'excluded_heads': final['excluded_heads'],
    'public_certificate_sha256': final['public_certificate_sha256'],
    'checks': checks,
    'semantic_checks': [{k: s[k] for k in ('project', 'purpose', 'head', 'pass', 'evidence')} for s in sem],
    'image_checks': image_checks,
    # evox16-attempt01 disk.jsonl: host D: free stayed 94.6 GiB through the whole compile; its verification and
    # delivery (ZIP copies, extraction growing build.vhdx) later used ~25 GiB. 45 keeps >= 10 GiB above that.
    'minimum_start_gib': {'host': 45, 'source': 10, 'output': 70},
    'emergency_minimum_gib': {'host': 10, 'source': 2, 'output': 2},
    'approved_by': 'Claude, on the user\'s instruction to review evox16, revert what is not needed and build evox17',
}
current, _ = check_capacity(ready)
ready['measured_free_gib'] = current
out = R / 'BUILD_READY.json'
with open(out, 'x') as f:
    f.write(json.dumps(ready, indent=2) + '\n')
print('BUILD_READY written:', out, '| checks', len(checks), '| free GiB', {k: round(v, 1) for k, v in current.items()})
