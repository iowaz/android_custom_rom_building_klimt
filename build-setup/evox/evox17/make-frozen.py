#!/usr/bin/env python3
"""Derive evox17-frozen.xml from evox16-frozen.xml: upstream heads everywhere except reviewed pins.

usage: make-frozen.py <evox16-frozen.xml> <evox17-frozen.xml> <changes.json>
Run on Windows or Linux with the GitHub CLI logged in. AOSP projects stay on their tag pins.
"""
import json, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

src, dst, report = sys.argv[1:4]
SHA = re.compile(r'[0-9a-f]{40}')
# path -> (remote, name, revision, upstream branch): evox15 identities and the reviewed klimt forks.
PINS = {
    'device/xiaomi/klimt': ('iowaz', 'android_device_xiaomi_klimt', '43b71ecbde010c3444dfb297e9dbd755b1b443c5', 'evox'),
    'kernel/xiaomi/klimt': None, 'kernel/xiaomi/klimt-prebuilt': None, 'vendor/xiaomi/klimt': None,
    'device/mediatek/sepolicy_vndr': None,  # evox15 117a8de2; 20 newer Lineage commits are not part of the 12.3 move
    'hardware/xiaomi': ('github', 'LineageOS/android_hardware_xiaomi', 'af5766acc6d6766eddeb52574996247128428ff6', 'lineage-24.0'),
    'hardware/interfaces': ('iowaz', 'hardware_interfaces', '11087c5b9457e65346d0324f5452c647fc080a7c', 'cnb-klimt'),
    'build/soong': ('iowaz', 'build_soong', 'ffe1ef057ccd96e9db801e3fb12860c67d9fb71f', 'evox16'),
    'frameworks/native': ('iowaz', 'frameworks_native', '2341752da7cc47dfb8ca54af82e8ae825bc53d5e', 'evox16'),
}
# path -> (remote, name, branch): projects whose evox16 entry was a local derivation or a fork.
UPSTREAM = {
    'packages/apps/Settings': ('evo', 'packages_apps_Settings', 'cnb'),
    'system/memory/libdmabufheap': ('github', 'LineageOS/android_system_memory_libdmabufheap', 'lineage-24.0'),
    'vendor/lineage': ('evo', 'vendor_evolution', 'cnb'),
    'libcore': ('aosp', 'platform/libcore', None),  # AOSP pin from the Evolution X manifest
}
LIBCORE_AOSP = '4ebfb391ee0109d16abe6e2bc965724b940928c5'

def attr(l, k):
    m = re.search(rf'\b{k}="([^"]*)"', l); return m.group(1) if m else None
def put(l, k, v):
    if v is None: return re.sub(rf'\s{k}="[^"]*"', '', l)
    if attr(l, k) is None: return l.replace('<project ', f'<project {k}="{v}" ', 1)
    return re.sub(rf'\b{k}="[^"]*"', f'{k}="{v}"', l, count=1)

text = open(src, encoding='utf-8').read()
remotes = {attr(l, 'name'): (attr(l, 'fetch'), attr(l, 'revision')) for l in text.splitlines() if l.strip().startswith('<remote ')}
default = next(l for l in text.splitlines() if l.strip().startswith('<default '))
default_remote, default_rev = attr(default, 'remote'), attr(default, 'revision')
def slug(remote, name):
    fetch = remotes[remote][0].rstrip('/')
    if not fetch.startswith('https://github.com'): return None
    owner = fetch.split('/')[3:]
    return '/'.join(owner + [name])
def branch_of(l, remote):
    up = (attr(l, 'upstream') or '')
    if up and not SHA.fullmatch(up): return up.replace('refs/heads/', '')
    rev = remotes[remote][1] if remotes[remote][1] else (default_rev if remote == default_remote else None)
    return rev.replace('refs/heads/', '') if rev and rev.startswith('refs/heads/') else None
def head(job):
    s, b = job
    r = subprocess.run(['gh', 'api', f'repos/{s}/commits/{b}', '-q', '.sha'], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None

lines = text.splitlines(); jobs = {}; plan = {}
for i, l in enumerate(lines):
    s = l.strip()
    if not s.startswith('<project '): continue
    path = attr(s, 'path') or attr(s, 'name'); remote = attr(s, 'remote') or default_remote
    if path in PINS:
        plan[i] = ('pin', path); continue
    if path in UPSTREAM:
        r, n, b = UPSTREAM[path]
        plan[i] = ('upstream', path, r, n, b)
        if b: jobs[(slug(r, n), b)] = None
        continue
    b = branch_of(s, remote); sl = slug(remote, attr(s, 'name'))
    if sl and b:
        plan[i] = ('track', path, remote, attr(s, 'name'), b); jobs[(sl, b)] = None
    else:
        plan[i] = ('keep', path)
with ThreadPoolExecutor(8) as ex:
    for job, sha in zip(jobs, ex.map(head, jobs)): jobs[job] = sha
missing = [j for j, v in jobs.items() if not v]
assert not missing, f'cannot resolve branch heads: {missing}'

changes = []
for i, p in plan.items():
    l = lines[i]; old = attr(l, 'revision'); path = p[1]
    if p[0] == 'pin':
        if PINS[path]:
            r, n, rev, b = PINS[path]
            for k, v in (('name', n), ('remote', None if r == default_remote else r), ('revision', rev), ('upstream', b), ('dest-branch', b)): l = put(l, k, v)
    elif p[0] == 'upstream':
        _, _, r, n, b = p
        rev = LIBCORE_AOSP if r == 'aosp' else jobs[(slug(r, n), b)]
        up = LIBCORE_AOSP if r == 'aosp' else b
        for k, v in (('name', n), ('remote', None if r == default_remote else r), ('revision', rev), ('upstream', up), ('dest-branch', up)): l = put(l, k, v)
    elif p[0] == 'track':
        _, _, r, n, b = p
        rev = jobs[(slug(r, n), b)]
        l = put(l, 'revision', rev)
        if SHA.fullmatch(attr(l, 'upstream') or ''):  # evox16 derivation recorded its base as upstream
            l = put(put(l, 'upstream', b), 'dest-branch', b)
    new = attr(l, 'revision')
    if new != old or l != lines[i]:
        changes.append({'path': path, 'old': old, 'new': new, 'old_line': lines[i].strip(), 'new_line': l.strip()})
    lines[i] = l
out = '\n'.join(lines) + '\n'
open(dst, 'w', encoding='utf-8', newline='\n').write(out)
json.dump(changes, open(report, 'w'), indent=1)
print(f'{out.count("<project ")} projects; {len(changes)} entries changed; {sum(c["old"]!=c["new"] for c in changes)} revisions changed')
for c in changes: print(f"  {c['path']:50} {c['old'][:10]} -> {c['new'][:10]}")
