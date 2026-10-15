"""Bind the five required source-gate semantic purposes to the frozen heads.

For each purpose, the original reviewed patch (Evox15 export or the Evox16/17
exact-base bundle) must reverse-apply cleanly against the current HEAD tree,
i.e. every hunk it introduced is present. Writes semantic_checks.json.
"""
from pathlib import Path
import hashlib, json, re, subprocess as sp, sys

S = Path('/mnt/wsl/evox/src')
DEV = S / 'device/xiaomi/klimt/patches'
OUT = Path(__file__).with_name('semantic_checks.json')
PURPOSES = [
    ('frameworks/base', 'Fix security vulnerabilities in PduParser.java'),
    ('frameworks/base', 'Fix potential OOM in PduParser by using stream skip'),
    ('packages/modules/Bluetooth', 'Remove unused ext_attrs from playerapplicationsetting_cb'),
    ('frameworks/opt/telephony', 'RESTRICT AUTOMERGE: Fix remote DoS in decodeWapPdu (b/517376969)'),
    ('frameworks/native', 'SMPTE 2094-50 capability guard'),
]
# The Evox16 bundle re-exports the Gralloc5 guard under an adapted subject.
ALIASES = {'SMPTE 2094-50 capability guard': ('libui: Preserve the supported SMPTE2094_50 metadata guard',
                                              "libui: Skip SMPTE 2094-50 on mappers that don't list it")}
final = json.loads(Path('/mnt/c/XiaomiBuilds/debug/evox17/FINAL_SOURCE.json').read_text())

def subject(patch):
    text = patch.read_text(errors='replace')
    m = re.search(r'^Subject: (?:\[PATCH[^\]]*\] )?(.*(?:\n [^\n]*)*)', text, re.M)
    return re.sub(r'\n ', ' ', m.group(1)).strip() if m else ''

def git(project, *args, check=True):
    return sp.run(['git', '-C', str(S / project), *args], text=True, stdout=sp.PIPE, stderr=sp.PIPE, check=check)

records, ok = [], True
for project, purpose in PURPOSES:
    head = git(project, 'rev-parse', 'HEAD').stdout.strip()
    assert head == final['heads'][project], project
    candidates = [p for tree in ('tree', 'tree-evox15') for p in sorted((DEV / tree / project).glob('*.patch'))
                  if subject(p).startswith((purpose, *ALIASES.get(purpose, ())))]
    rec = {'project': project, 'purpose': purpose, 'head': head, 'pass': False, 'candidates': [str(p) for p in candidates]}
    for patch in candidates:
        res = git(project, 'apply', '--check', '--reverse', str(patch), check=False)
        rec.setdefault('attempts', []).append({'patch': str(patch), 'sha256': hashlib.sha256(patch.read_bytes()).hexdigest(),
                                               'reverse_apply_exit': res.returncode, 'stderr': res.stderr[-600:]})
        if res.returncode == 0:
            files = re.findall(r'^diff --git a/(\S+) b/', patch.read_text(errors='replace'), re.M)
            rec.update({'pass': True, 'evidence': f'{patch.relative_to(S)} (sha256 {hashlib.sha256(patch.read_bytes()).hexdigest()}) '
                        f'reverse-applies cleanly at {project}@{head}: every hunk is present in the frozen tree '
                        f'({len(files)} files: {", ".join(files)}).'})
            break
    ok &= rec['pass']
    records.append(rec)
    print('PASS' if rec['pass'] else 'FAIL', project, '|', purpose, flush=True)
OUT.write_text(json.dumps(records, indent=2) + '\n')
sys.exit(0 if ok else 1)
