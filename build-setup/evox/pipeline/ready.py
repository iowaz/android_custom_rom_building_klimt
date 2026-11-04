#!/usr/bin/env python3
"""Write BUILD_READY.json for a build, only if every gate passes. No build is started.

usage: KLIMT_BUILD=20261105 python3 -B ready.py <frozen-manifest.xml> [--gate NAME=EVIDENCE_PATH ...]

Writes, in diagnostics/builds/<build>/: FINAL_SOURCE.json, semantic_checks.json, BUILD_READY.json.
Gates:
  - every project HEAD equals the frozen manifest, and every worktree is clean; a project listed in the device
    tree's patches/PATCHES.json (read at the device tree's frozen pin) is pinned at its upstream base and must be
    at its final_head (see controller.effective_heads);
  - `repo manifest -r` of the live tree resolves to the same heads;
  - the device patches are applied: `patches/apply.py <tree> --check` exits 0 and reports FINAL for exactly the
    projects in PATCHES.json;
  - the four historical security fixes and the SMPTE 2094-50 guard are in the source (reference patches in
    semantic-patches/ and the device tree's patches/<project>/ reverse-apply at the live heads);
  - build.sh cleans the staging directories before updatepackage;
  - the seven image checks are registered with their exact hash and passed their tests on Linux;
  - every --gate evidence file exists and is not empty (reviews, negative tests, ...).
Recorded as information, not gates: the platform security patch level of the frozen source, and the LineageOS
security-bulletin review state (topic C_asb_<YYYY-MM>) for the current month ("unavailable" without network).
"""
import argparse, json, re, shutil, subprocess as sp, time, urllib.request
from pathlib import Path

from controller import (B, S, D, BUILD, DEVICE, PATCHES_JSON, manifest_heads, live_heads, patch_bundle,
                        effective_heads, check_capacity, sha)

PURPOSES = [
    ('frameworks/base', 'Fix security vulnerabilities in PduParser.java'),
    ('frameworks/base', 'Fix potential OOM in PduParser by using stream skip'),
    ('packages/modules/Bluetooth', 'Remove unused ext_attrs from playerapplicationsetting_cb'),
    ('frameworks/opt/telephony', 'RESTRICT AUTOMERGE: Fix remote DoS in decodeWapPdu (b/517376969)'),
    ('frameworks/native', 'SMPTE 2094-50 capability guard'),
]
# The SMPTE guard has been exported under two subjects; the current one is the device patch under
# patches/frameworks/native/.
ALIASES = {'SMPTE 2094-50 capability guard': ('libui: Preserve the supported SMPTE2094_50 metadata guard',
                                              "libui: Skip SMPTE 2094-50 on mappers that don't list it")}
# Reference patches, copied from the device tree's retired patches/tree and patches/tree-evox15 (SOURCES.txt).
SEMANTIC_PATCHES = B / 'semantic-patches'
EXCLUDED = ['kernel/xiaomi/klimt', 'kernel/xiaomi/klimt-prebuilt', 'vendor/xiaomi/klimt', 'hardware/xiaomi',
            'device/mediatek/sepolicy_vndr']
CERTS = ['platform', 'releasekey', 'shared', 'media', 'networkstack']
RELEASE = 'cp2a'
GERRIT = 'https://review.lineageos.org/changes/'
APPLY_STATES = ('FINAL', 'APPLIED', 'MISMATCH', 'DIRTY', 'HASH')

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

def reference_patches(project, purpose, roots):
    """Patches under <root>/<project>/ whose subject starts with the purpose (or one of its aliases)."""
    return [p for root in roots for p in sorted((Path(root) / project).glob('*.patch'))
            if subject(p).startswith((purpose, *ALIASES.get(purpose, ())))]

def semantic(heads):
    """Each purpose is proven by its reference patch reverse-applying cleanly at the live head."""
    records = []
    roots = (SEMANTIC_PATCHES, S / DEVICE / 'patches')
    for project, purpose in PURPOSES:
        head = git(project, 'rev-parse', 'HEAD').stdout.strip()
        assert head == heads[project], project
        rec = {'project': project, 'purpose': purpose, 'head': head, 'pass': False}
        for patch in reference_patches(project, purpose, roots):
            if git(project, 'apply', '--check', '--reverse', str(patch), ok=False).returncode == 0:
                where = patch.relative_to(S) if patch.is_relative_to(S) else patch.relative_to(B.parent.parent.parent)
                rec['pass'] = True
                rec['evidence'] = f'{where} (sha256 {sha(patch)}) reverse-applies cleanly at {project}@{head}'
                break
        records.append(rec)
    return records

def apply_report(stdout):
    """`apply.py --check` lines -> [(state, project)]; an unknown line is kept as (None, line)."""
    result = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        m = re.match(r'(' + '|'.join(APPLY_STATES) + r')\b:?\s+(\S+)', line.strip())
        result.append((m.group(1), m.group(2)) if m else (None, line.strip()))
    return result

def bundle_final(returncode, stdout, bundle):
    """True iff apply.py --check exited 0 and reported FINAL, once, for exactly the PATCHES.json projects."""
    report = apply_report(stdout)
    projects = [p for _, p in report]
    return (returncode == 0 and bool(report) and all(s == 'FINAL' for s, _ in report)
            and len(projects) == len(set(projects)) and set(projects) == set(bundle))

def textproto_value(text):
    m = re.search(r'string_value:\s*"([^"]*)"', text)
    return m.group(1) if m else None

def security_patch_level(frozen):
    """PLATFORM_SECURITY_PATCH of the frozen source. Android 17 takes it from the RELEASE_PLATFORM_SECURITY_PATCH
    release flag (vendor/lineage's value overrides build/release's); build/make core/version_defaults.mk only
    carries it on older trees. Read at the frozen pins, not from the worktrees. Information only."""
    sources = [('vendor/lineage', f'release/flag_values/{RELEASE}/RELEASE_PLATFORM_SECURITY_PATCH.textproto', textproto_value),
               ('build/release', f'flag_values/{RELEASE}/RELEASE_PLATFORM_SECURITY_PATCH.textproto', textproto_value),
               ('build/make', 'core/version_defaults.mk',
                lambda t: (re.search(r'^\s*PLATFORM_SECURITY_PATCH\s*:?=\s*(\d{4}-\d{2}-\d{2})\s*$', t, re.M) or [None, None])[1])]
    found = []
    for project, path, parse in sources:
        if project not in frozen:
            continue
        r = git(project, 'show', f'{frozen[project]}:{path}', ok=False)
        value = parse(r.stdout) if r.returncode == 0 else None
        if value:
            found.append({'project': project, 'pin': frozen[project], 'file': path, 'value': value})
    return {'platform_security_patch': found[0]['value'] if found else 'unknown', 'sources': found,
            'note': 'the device tree reports its own fixed ro.build.version.security_patch (lineage_klimt.mk)'}

def gerrit_count(query, fetch, page=500, pages=10):
    """Number of changes for a Gerrit query, following _more_changes. fetch(url) returns the raw body."""
    total, branches = 0, {}
    for n in range(pages):
        body = fetch(f'{GERRIT}?q={query}&n={page}&S={n * page}')
        first, _, rest = body.partition('\n')
        if first.strip() != ")]}'":
            raise ValueError('unexpected Gerrit response prefix')
        changes = json.loads(rest)
        total += len(changes)
        for c in changes:
            branches[c.get('branch', '?')] = branches.get(c.get('branch', '?'), 0) + 1
        if not changes or not changes[-1].get('_more_changes'):
            return total, branches
    raise ValueError('more than %d changes' % (page * pages))

def bulletin_state(month, fetch=None):
    """LineageOS review state of the security bulletin for <month> (YYYY-MM). Never raises."""
    fetch = fetch or (lambda url: urllib.request.urlopen(url, timeout=30).read().decode())
    topic = 'C_asb_' + month
    result = {'topic': topic, 'checked': time.strftime('%Y-%m-%dT%H:%M:%S%z')}
    try:
        for status in ('open', 'merged'):
            count, branches = gerrit_count(f'topic:{topic}+status:{status}', fetch)
            result[status] = count
            result[status + '_by_branch'] = branches
        result['state'] = ('not started' if result['open'] == result['merged'] == 0 else
                           'merged' if result['open'] == 0 else 'in review')
    except Exception as e:  # network or format: recorded, never a gate
        result.update(state='unavailable', error=f'{type(e).__name__}: {e}'[:300])
    return result

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('snapshot')
    ap.add_argument('--gate', action='append', default=[], help='NAME=EVIDENCE_PATH')
    args = ap.parse_args()
    D.mkdir(parents=True, exist_ok=True)
    snapshot = Path(args.snapshot).resolve()
    frozen_path = D / f'{BUILD}-frozen.xml'
    if snapshot != frozen_path:
        shutil.copyfile(snapshot, frozen_path)  # the build's own copy; the controller pins its hash
    frozen = manifest_heads(frozen_path.read_bytes())
    bundle = patch_bundle(frozen)          # device/xiaomi/klimt:patches/PATCHES.json at the frozen device pin
    heads = effective_heads(frozen, bundle)
    live_heads(heads)  # raises on HEAD drift or a dirty/untracked project
    resolved = D / 'manifest-resolved.xml'
    sp.run(['repo', 'manifest', '-r', '-o', str(resolved)], cwd=S, check=True, stdout=sp.DEVNULL)
    check('frozen full graph, clean worktrees, live repo manifest agrees',
          manifest_heads(resolved.read_bytes()) == heads,
          f'{frozen_path}: {len(heads)} projects, sha256 {sha(frozen_path)}; live HEADs and `repo manifest -r` match, '
          f'{len(bundle)} patched projects at their PATCHES.json final_head over the frozen base')
    keys = S / 'vendor/evolution-priv/keys'
    certs = {n: sha(keys / f'{n}.x509.pem') for n in CERTS}
    apply_py = S / DEVICE / 'patches/apply.py'
    check('device patches present', bool(bundle) and apply_py.is_file(), f'{DEVICE}@{frozen[DEVICE]}: {PATCHES_JSON}, patches/apply.py')
    apply = sp.run(['python3', '-B', str(apply_py), str(S), '--check'], capture_output=True, text=True)
    check('device patches applied (apply.py --check: every project FINAL)', bundle_final(apply.returncode, apply.stdout, bundle),
          f'patches/apply.py --check exit {apply.returncode}: ' + '; '.join(l.strip() for l in apply.stdout.splitlines() if l.strip())
          + (' | stderr: ' + apply.stderr.strip()[-300:] if apply.stderr.strip() else ''))
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
    patched = {p: {k: r.get(k) for k in ('class', 'purpose', 'base', 'final_head', 'final_tree')} for p, r in bundle.items()}
    security = dict(security_patch_level(frozen), bulletin=bulletin_state(time.strftime('%Y-%m')))
    final = dict(build=BUILD, snapshot=str(frozen_path), snapshot_sha256=sha(frozen_path), projects=len(heads), heads=frozen,
                 effective_heads=heads, patched_projects=patched,
                 excluded_heads={p: frozen[p] for p in EXCLUDED}, public_certificate_sha256=certs, all_worktrees_clean=True,
                 security=security, time=time.time())
    (D / 'FINAL_SOURCE.json').write_text(json.dumps(final, indent=1) + '\n')
    ready = {
        'approved': True, 'runtime_unvalidated': True, 'target': 'lineage_klimt-cp2a-user', 'build': BUILD,
        'snapshot': str(frozen_path), 'sha256': sha(frozen_path),
        'reviewed_project_heads': frozen, 'effective_project_heads': heads,
        'patch_bundle': {'device_head': frozen[DEVICE], 'file': PATCHES_JSON, 'projects': patched},
        'excluded_heads': final['excluded_heads'],
        'public_certificate_sha256': certs, 'checks': checks,
        'semantic_checks': [{k: s[k] for k in ('project', 'purpose', 'head', 'pass', 'evidence')} for s in sem],
        'image_checks': image_checks,
        'security': security,  # information, not a gate
        # evox16/17: the compile never grew D:; verification and delivery used ~25 GiB.
        # evox27: output 45 (was 70). evox26 went from 86 to 51 GiB free on the build disk, all of it the
        # verifier's extraction (compare/evox26, 35 GiB); ccache is capped at 20 GiB and full, and out/ is
        # rewritten in place. build.vhdx is at 629 of its 640 GiB, so D: can lose at most ~11 GiB.
        'minimum_start_gib': {'host': 45, 'source': 10, 'output': 45},
        'emergency_minimum_gib': {'host': 10, 'source': 2, 'output': 2},
    }
    current, _ = check_capacity(ready)
    ready['measured_free_gib'] = current
    out = D / 'BUILD_READY.json'
    with open(out, 'x') as f:
        f.write(json.dumps(ready, indent=2) + '\n')
    b = security['bulletin']
    print('BUILD_READY written:', out, '| checks', len(checks), '| free GiB', {k: round(v, 1) for k, v in current.items()},
          '| SPL', security['platform_security_patch'], '|', b['topic'], b['state'],
          '' if b['state'] == 'unavailable' else f"(open {b['open']}, merged {b['merged']})")

if __name__ == '__main__':
    main()
