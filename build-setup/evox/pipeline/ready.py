#!/usr/bin/env python3
"""Write BUILD_READY.json for a build, only if every gate passes. No build is started.

usage: KLIMT_BUILD=evox18 python3 -B ready.py <frozen-manifest.xml> [--gate NAME=EVIDENCE_PATH ...]

Writes, in diagnostics/builds/<build>/: FINAL_SOURCE.json, semantic_checks.json, BUILD_READY.json.
Gates:
  - every project HEAD equals the frozen manifest, and every worktree is clean;
  - `repo manifest -r` of the live tree resolves to the same heads;
  - the device tree's patches/tree is already applied (apply.py reports only final trees);
  - the four historical security fixes and the SMPTE 2094-50 guard are in the frozen source;
  - build.sh cleans the staging directories before updatepackage;
  - the seven image checks are registered with their exact hash and passed their tests on Linux;
  - every --gate evidence file exists and is not empty (reviews, negative tests, ...).
"""
import argparse, hashlib, json, re, shutil, subprocess as sp, sys, time
from pathlib import Path

import paths
from controller import B, S, D, BUILD, manifest_heads, live_heads, check_capacity, sha

PURPOSES = [
    ('frameworks/base', 'Fix security vulnerabilities in PduParser.java'),
    ('frameworks/base', 'Fix potential OOM in PduParser by using stream skip'),
    ('packages/modules/Bluetooth', 'Remove unused ext_attrs from playerapplicationsetting_cb'),
    ('frameworks/opt/telephony', 'RESTRICT AUTOMERGE: Fix remote DoS in decodeWapPdu (b/517376969)'),
    ('frameworks/native', 'SMPTE 2094-50 capability guard'),
]
# The SMPTE guard has been exported under two subjects.
ALIASES = {'SMPTE 2094-50 capability guard': ('libui: Preserve the supported SMPTE2094_50 metadata guard',
                                              "libui: Skip SMPTE 2094-50 on mappers that don't list it")}
EXCLUDED = ['kernel/xiaomi/klimt', 'kernel/xiaomi/klimt-prebuilt', 'vendor/xiaomi/klimt', 'hardware/xiaomi',
            'device/mediatek/sepolicy_vndr']
CERTS = ['platform', 'releasekey', 'shared', 'media', 'networkstack']

checks = []
def check(name, condition, evidence):
    if not condition:
        raise SystemExit('GATE NOT MET: ' + name + ' :: ' + evidence)
    checks.append({'name': name, 'pass': True, 'evidence': evidence})

def git(project, *args, ok=True):
    return sp.run(['git', '-C', str(S / project), *args], text=True, stdout=sp.PIPE, stderr=sp.PIPE, check=ok)

def subject(patch):
    m = re.search(r'^Subject: (?:\[PATCH[^\]]*\] )?(.*(?:\n [^\n]*)*)', patch.read_text(errors='replace'), re.M)
    return re.sub(r'\n ', ' ', m.group(1)).strip() if m else ''

def semantic(heads):
    """Each purpose is proven by the original patch reverse-applying cleanly at the frozen head."""
    records = []
    for project, purpose in PURPOSES:
        head = git(project, 'rev-parse', 'HEAD').stdout.strip()
        assert head == heads[project], project
        patches = [p for tree in ('tree', 'tree-evox15') for p in sorted((S / 'device/xiaomi/klimt/patches' / tree / project).glob('*.patch'))
                   if subject(p).startswith((purpose, *ALIASES.get(purpose, ())))]
        rec = {'project': project, 'purpose': purpose, 'head': head, 'pass': False}
        for patch in patches:
            if git(project, 'apply', '--check', '--reverse', str(patch), ok=False).returncode == 0:
                rec['pass'] = True
                rec['evidence'] = f'{patch.relative_to(S)} (sha256 {sha(patch)}) reverse-applies cleanly at {project}@{head}'
                break
        records.append(rec)
    return records

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('snapshot')
    ap.add_argument('--gate', action='append', default=[], help='NAME=EVIDENCE_PATH')
    args = ap.parse_args()
    D.mkdir(parents=True, exist_ok=True)
    snapshot = Path(args.snapshot).resolve()
    frozen = D / f'{BUILD}-frozen.xml'
    if snapshot != frozen:
        shutil.copyfile(snapshot, frozen)  # the build's own copy; the controller pins its hash
    heads = manifest_heads(frozen.read_bytes())
    live_heads(heads)  # raises on HEAD drift or a dirty/untracked project
    resolved = D / 'manifest-resolved.xml'
    sp.run(['repo', 'manifest', '-r', '-o', str(resolved)], cwd=S, check=True, stdout=sp.DEVNULL)
    check('frozen full graph, clean worktrees, live repo manifest agrees',
          manifest_heads(resolved.read_bytes()) == heads,
          f'{frozen}: {len(heads)} projects, sha256 {sha(frozen)}; live HEADs and `repo manifest -r` match')
    keys = S / 'vendor/evolution-priv/keys'
    certs = {n: sha(keys / f'{n}.x509.pem') for n in CERTS}
    apply = sp.run(['python3', str(S / 'device/xiaomi/klimt/patches/tree/apply.py'), str(S)], capture_output=True, text=True)
    lines = [l for l in apply.stdout.splitlines() if l.strip()]
    check('device patch bundle already final', apply.returncode == 0 and lines and all(l.startswith('Equivalent full final tree') for l in lines),
          'patches/tree/apply.py: ' + '; '.join(lines))
    sem = semantic(heads)
    (D / 'semantic_checks.json').write_text(json.dumps(sem, indent=2) + '\n')
    check('five semantic source purposes at the frozen heads', len(sem) == 5 and all(s['pass'] for s in sem), str(D / 'semantic_checks.json'))
    build = (B / 'build.sh').read_text()
    check('build wrapper cleans staging before updatepackage',
          build.index('m -j12 installclean') < build.index('m -j12 updatepackage') and 'STAGING_NOT_CLEAN' in build, str(B / 'build.sh'))
    image_checks = json.loads((B / 'image-checks/IMAGE_CHECKS.json').read_text())
    for c in image_checks:
        assert Path(c['argv'][1]).resolve() == (B / 'image-checks/check_image.py').resolve(), c['argv']
        assert sha(Path(c['argv'][1])) == c['script_sha256'], c['name']
    tests = json.loads((B / 'image-checks/TEST_RESULTS.linux.json').read_text())
    check('seven image checks registered and self-tested on Linux',
          len(image_checks) == 7 and tests['passed'] and tests['skipped'] == 0 and tests['check_image_py_sha256'] == image_checks[0]['script_sha256'],
          f"{B / 'image-checks/IMAGE_CHECKS.json'} (sha {image_checks[0]['script_sha256'][:12]}); {tests['tests_run']} Linux tests pass")
    for g in args.gate:
        name, _, path = g.partition('=')
        p = Path(path)
        check(name, p.is_file() and p.stat().st_size > 0, str(p))
    final = dict(build=BUILD, snapshot=str(frozen), snapshot_sha256=sha(frozen), projects=len(heads), heads=heads,
                 excluded_heads={p: heads[p] for p in EXCLUDED}, public_certificate_sha256=certs, all_worktrees_clean=True, time=time.time())
    (D / 'FINAL_SOURCE.json').write_text(json.dumps(final, indent=1) + '\n')
    ready = {
        'approved': True, 'runtime_unvalidated': True, 'target': 'lineage_klimt-cp2a-user', 'build': BUILD,
        'snapshot': str(frozen), 'sha256': sha(frozen),
        'reviewed_project_heads': heads, 'excluded_heads': final['excluded_heads'],
        'public_certificate_sha256': certs, 'checks': checks,
        'semantic_checks': [{k: s[k] for k in ('project', 'purpose', 'head', 'pass', 'evidence')} for s in sem],
        'image_checks': image_checks,
        # evox16/17: the compile never grew D:; verification and delivery used ~25 GiB.
        'minimum_start_gib': {'host': 45, 'source': 10, 'output': 70},
        'emergency_minimum_gib': {'host': 10, 'source': 2, 'output': 2},
    }
    current, _ = check_capacity(ready)
    ready['measured_free_gib'] = current
    out = D / 'BUILD_READY.json'
    with open(out, 'x') as f:
        f.write(json.dumps(ready, indent=2) + '\n')
    print('BUILD_READY written:', out, '| checks', len(checks), '| free GiB', {k: round(v, 1) for k, v in current.items()})

if __name__ == '__main__':
    main()
