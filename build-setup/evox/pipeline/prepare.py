#!/usr/bin/env python3
"""Prepare the source tree for one build, step by step. No build is started and nothing is pushed.

usage: python3 -B prepare.py <step> <build> [--previous <build>] [--dry-run]

Steps, in order (each refuses to run before the one it needs, twice, or on a dirty/unexpected tree, and
writes its record to diagnostics/builds/<build>/preparation/):
  upstream      record the current heads (they must be the previous build's source), fetch the Evolution X
                manifest `cnb` head into ~/evox-upstream-check/mf, commit its default.xml and snippets on the
                local branch `klimt` of .repo/manifests with klimt-live.xml (the klimt projects only, no
                extend-project) and point .repo/manifest.xml at it. Does not sync.
  move-renamed  move aside (never delete) projects whose repository name changed at the same path, so repo can
                clone them again (evox27: repo fails with "hooks is different" otherwise).
  sync          repo sync to the new manifest, then compare with the previous snapshot -> UPSTREAM_CHANGES.json.
                About an hour: run it from a background shell.
  patch         device/xiaomi/klimt/patches/apply.py: the klimt patches onto local branch `klimt` of each
                patched project. When Evolution X has rebased a patched project (apply.py: MISMATCH), the
                recorded patches are first replayed with `git am -3` on the synced head, re-exported with
                patches/export.py and committed on the device tree's local cnb. Only a real conflict stops
                here: that patch needs a hand port.
  label         device tree commit (local branch cnb) that sets the kernel label in configs/kernel/metadata.config:
                the previous build's label is replaced, evox31 -> 20261105 and ab31 -> ab20261105.
  freeze        diagnostics/builds/<build>/<build>-frozen.xml = `repo manifest -r` with every patched project
                pinned at its upstream base, copied to manifests/snapshots/<build>.xml and .repo/manifests.
Then: ready.py <frozen> -> start.sh -> promote.py. The device commit (iowaz cnb) is pushed only with the owner's OK.
"""
import argparse, hashlib, json, os, re, shutil, subprocess as sp, sys, time
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape

import paths

S = paths.SRC
M = S / '.repo/manifests'
DEVICE = 'device/xiaomi/klimt'
KERNEL = 'kernel/xiaomi/klimt'
PREBUILT = 'kernel/xiaomi/klimt-prebuilt'
VENDOR = 'vendor/xiaomi/klimt'
LINEAGE_DEPS = {'hardware/xiaomi': 'LineageOS/android_hardware_xiaomi',
                'device/mediatek/sepolicy_vndr': 'LineageOS/android_device_mediatek_sepolicy_vndr'}
KLIMT = [DEVICE, KERNEL, PREBUILT, VENDOR, *LINEAGE_DEPS]
IOWAZ = {DEVICE, KERNEL, VENDOR}         # the only iowaz repositories: no ROM-source forks since 2026-11-04
LIVE = 'klimt-live.xml'
COMMITTER = ('Diogo Casteluber Laass', '4793368+iowaz@users.noreply.github.com')  # same identity apply.py forces
REBASE_BRANCH = 'klimt-rebase'
UPSTREAM_URL = 'https://github.com/Evolution-X/manifest'
SHA = re.compile(r'[0-9a-f]{40}')
STEPS = ['upstream', 'move-renamed', 'sync', 'patch', 'label', 'freeze']
RECORD = {'upstream': 'UPSTREAM.json', 'move-renamed': 'MOVED_PROJECTS.json', 'sync': 'SYNC.json',
          'patch': 'PATCH.json', 'label': 'LABEL.json', 'freeze': 'FREEZE.json'}

# ---- pure helpers (unit-tested in tests.py) ----

def build_key(name):
    """Order of builds: evox1 ... evox31, then the date builds (20261105 < 20261105.2 < 20261106)."""
    if not paths.is_build(name):
        raise ValueError('Invalid build name: ' + repr(name))
    m = paths.HISTORY_BUILD.fullmatch(name)
    if m:
        return (0, int(m.group(1)), 0)
    d = paths.DATE_BUILD.fullmatch(name)
    return (1, int(d.group(1)), int(d.group(2) or 1))

def previous_build(build, names):
    """The newest build before <build> among <names> (snapshot file stems); others are ignored."""
    older = [n for n in names if paths.is_build(n) and build_key(n) < build_key(build)]
    if not older:
        raise ValueError('No build before ' + build)
    return max(older, key=build_key)

def attr(line, key):
    m = re.search(rf'\s{re.escape(key)}="([^"]*)"', line)
    return m.group(1) if m else None

def put(line, key, value):
    if attr(line, key) is None:
        raise ValueError('No ' + key + ' attribute in ' + line.strip())
    return re.sub(rf'(\s{re.escape(key)}=)"[^"]*"', lambda m: m.group(1) + '"' + value + '"', line, count=1)

def fix_github_fetch(text):
    """evox30: Evolution X's default.xml gives the github remote fetch="..", which resolves to the local manifest
    clone. Make it https://github.com. Returns (text, changed)."""
    pattern = re.compile(r'(<remote\s+name="github"\s+fetch=)"\.\."')
    found = pattern.findall(text)
    if len(found) > 1:
        raise ValueError('More than one github remote in default.xml')
    return pattern.sub(r'\1"https://github.com"', text), bool(found)

def _project(element):
    return '  <project ' + ' '.join(f'{k}="{escape(v, {chr(34): "&quot;"})}"' for k, v in element.attrib.items()) + ' />\n'

def live_manifest(previous_text):
    """The local live manifest: Evolution X default.xml plus the klimt projects only. Device: iowaz cnb. Kernel,
    kernel-prebuilt and vendor: exactly as in the previous live manifest. hardware/xiaomi and
    device/mediatek/sepolicy_vndr: LineageOS lineage-24.0. No extend-project: no ROM-source forks."""
    root = ET.fromstring(previous_text.encode())
    keep = {}
    for p in root.findall('project'):
        path = p.get('path') or p.get('name')
        if path in (KERNEL, PREBUILT, VENDOR):
            if path in keep or p.get('remote') not in ('iowaz', 'misakazip'):
                raise ValueError('Unexpected previous live entry for ' + path)
            keep[path] = p
    if set(keep) != {KERNEL, PREBUILT, VENDOR}:
        raise ValueError('Previous live manifest lacks ' + str(sorted({KERNEL, PREBUILT, VENDOR} - set(keep))))
    out = ['<?xml version="1.0" encoding="UTF-8"?>\n',
           '<!-- Written by build-setup/evox/pipeline/prepare.py upstream: Evolution X cnb plus the klimt projects.\n'
           '     No ROM-source forks; the klimt patches are in device/xiaomi/klimt/patches (apply.py). -->\n',
           '<manifest>\n', '  <include name="default.xml" />\n',
           '  <remote name="iowaz" fetch="https://github.com/iowaz" />\n',
           '  <remote name="misakazip" fetch="https://github.com/misakazip-dev" />\n',
           f'  <project name="android_device_xiaomi_klimt" path="{DEVICE}" remote="iowaz" revision="cnb" />\n']
    out += [_project(keep[p]) for p in (KERNEL, PREBUILT, VENDOR)]
    out += [f'  <project path="{p}" name="{n}" remote="github" revision="lineage-24.0" />\n' for p, n in LINEAGE_DEPS.items()]
    out.append('</manifest>\n')
    return ''.join(out)

def project_map(text):
    return {p.get("path") or p.get("name"): dict(p.attrib) for p in ET.fromstring(text.encode()).findall("project")}

def renamed_projects(old, new):
    """(renamed, added, removed): paths whose repository name changed, and paths only in one manifest."""
    changed = sorted(p for p in old.keys() & new.keys() if old[p].get('name') != new[p].get('name'))
    return changed, sorted(new.keys() - old.keys()), sorted(old.keys() - new.keys())

_TOKEN = r'(?<![A-Za-z0-9_.]){}(?![A-Za-z0-9_]|\.\d)'

def relabel(text, previous, build):
    """metadata.config for <build>: the previous build name (once, in the comment) and kernel label (twice: the
    comment and CONFIG_LOCALVERSION) are replaced. Anything else is an error."""
    old_label, new_label = paths.kernel_label(previous), paths.kernel_label(build)
    name = re.compile(_TOKEN.format(re.escape(previous)))
    label = re.compile(_TOKEN.format(re.escape(old_label)))
    if len(name.findall(text)) != 1 or len(label.findall(text)) != 2:
        raise ValueError(f'metadata.config must name {previous} once and {old_label} twice')
    if len(re.findall(r'^CONFIG_LOCALVERSION="[^"]*-' + re.escape(old_label) + '"$', text, re.M)) != 1:
        raise ValueError('CONFIG_LOCALVERSION does not end in -' + old_label)
    return label.sub(new_label, name.sub(build, text))

def freeze_manifest(resolved, bundle, build):
    """`repo manifest -r` text -> frozen text: each patched project (at its final_head in the live tree) is pinned
    at its upstream base. Only the klimt repositories may come from iowaz."""
    lines = resolved.splitlines(keepends=True)
    seen = set()
    for i, line in enumerate(lines):
        s = line.strip()
        if not s.startswith('<project '):
            continue
        path = attr(s, 'path') or attr(s, 'name')
        if attr(s, 'remote') == 'iowaz' and path not in IOWAZ:
            raise ValueError('ROM-source fork in the live tree: ' + path)
        if path in bundle:
            r = bundle[path]
            if attr(s, 'revision') != r['final_head']:
                raise ValueError(f'{path} is not at its PATCHES.json final_head (run prepare.py patch)')
            if not attr(s, 'upstream') or SHA.fullmatch(attr(s, 'upstream')):
                raise ValueError(path + ' has no upstream branch')
            lines[i] = put(line, 'revision', r['base'])
            seen.add(path)
    if seen != set(bundle):
        raise ValueError('Patched projects missing from the manifest: ' + str(sorted(set(bundle) - seen)))
    text = ''.join(lines)
    note = (f'  <!-- {build}: frozen source. The projects in {DEVICE}/patches/PATCHES.json are pinned at their upstream\n'
            f'       base; after a sync, run {DEVICE}/patches/apply.py to put them at their final_head. -->\n')
    head, sep, tail = text.partition('<manifest>\n')
    if not sep:
        raise ValueError('No <manifest> element line')
    return head + sep + note + tail

def comparison_base(path, old_entry, klimt=KLIMT):
    """What a project's new revision is compared with: its previous pin. A fork-era pin (iowaz remote outside
    the klimt repositories, up to evox31) is compared through its merge base with the new revision."""
    if old_entry is None:
        return None, 'added'
    if old_entry.get('remote') == 'iowaz' and path not in klimt:
        return old_entry.get('revision'), 'fork'
    return old_entry.get('revision'), 'pin'

# ---- tree helpers ----

def git(path, *args, check=True):
    r = sp.run(['git', '-C', str(path), *args], text=True, capture_output=True)
    if check and r.returncode:
        raise RuntimeError(f'git -C {path} {" ".join(args)}: {r.stderr.strip()}')
    return r.stdout.strip() if check else r

def clean(path):
    status = git(path, 'status', '--porcelain', '--untracked-files=normal')
    if status:
        raise RuntimeError('Dirty: ' + str(path) + '\n' + status[:500])

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

class Prep:
    def __init__(self, build, previous, dry_run):
        self.build, self.dry = build, dry_run
        self.previous = previous or previous_build(build, [p.stem for p in paths.SNAPSHOTS.glob('*.xml')])
        self.out = paths.for_build(build)['preparation']
        self.snapshot = paths.SNAPSHOTS / f'{self.previous}.xml'
        if not self.snapshot.is_file():
            raise RuntimeError('Previous snapshot missing: ' + str(self.snapshot))

    def done(self, step):
        return (self.out / RECORD[step]).is_file()

    def record(self, step, data, ok=True):
        """Success: <RECORD>.json, written once. Failure: a timestamped .failed file; the step may run again."""
        self.out.mkdir(parents=True, exist_ok=True)
        data = dict(step=step, build=self.build, previous=self.previous, ok=ok, time=time.strftime('%Y-%m-%dT%H:%M:%S%z'), **data)
        name = RECORD[step] if ok else RECORD[step].replace('.json', time.strftime('.failed.%Y%m%d-%H%M%S.json'))
        with open(self.out / name, 'x') as f:
            f.write(json.dumps(data, indent=2) + '\n')
        return self.out / name

    def require(self, step):
        i = STEPS.index(step)
        if not self.dry and self.done(step):
            raise RuntimeError(f'{step} already done for {self.build}: {self.out / RECORD[step]}')
        for before in STEPS[:i]:
            if not self.done(before):
                raise RuntimeError(f'Run prepare.py {before} {self.build} first')
        if not (S / '.repo').is_dir():
            raise RuntimeError('No repo tree at ' + str(S))
        clean(M)
        for p in KLIMT:
            clean(S / p)

    def on_klimt_branch(self):
        if git(M, 'branch', '--show-current') != 'klimt':
            raise RuntimeError('.repo/manifests is not on its local branch klimt')

    def bundle(self, rev='HEAD'):
        import controller
        show = git(S / DEVICE, 'show', f'{rev}:{controller.PATCHES_JSON}', check=False)
        if show.returncode:
            raise RuntimeError(f'{DEVICE}@{rev} has no {controller.PATCHES_JSON}')
        return controller.parse_patch_bundle(show.stdout)

    # ---- steps ----

    def upstream(self):
        import controller
        self.require('upstream')
        frozen = controller.manifest_heads(self.snapshot.read_bytes())
        expected = controller.expected_heads(frozen)
        # The tree must still be the previous build's source. The device tree may have moved forward (new klimt
        # commits between builds), never sideways.
        device = git(S / DEVICE, 'rev-parse', 'HEAD')
        if device != frozen[DEVICE] and git(S / DEVICE, 'merge-base', '--is-ancestor', frozen[DEVICE], device, check=False).returncode:
            raise RuntimeError(f'{DEVICE} HEAD {device} does not descend from the {self.previous} pin {frozen[DEVICE]}')
        controller.live_heads({p: h for p, h in expected.items() if p != DEVICE})
        clean(S / DEVICE)
        previous_live = M / LIVE if (M / LIVE).is_file() else M / f'{self.previous}-live.xml'
        live = live_manifest(previous_live.read_text())
        up = paths.UPSTREAM_MANIFEST
        if self.dry:
            print(f'previous {self.previous}: {len(frozen)} projects at their recorded heads; device {device}')
            print(f'would fetch {UPSTREAM_URL} cnb into {up}, commit default.xml + snippets + {LIVE} on .repo/manifests branch klimt')
            print(live, end='')
            return
        self.out.mkdir(parents=True, exist_ok=True)
        sp.run(['repo', 'manifest', '-r', '-o', str(self.out / 'before-resolved.xml')], cwd=S, check=True)
        shutil.copyfile(S / '.repo/manifest.xml', self.out / 'manifest-wrapper-before.xml')
        shutil.copyfile(previous_live, self.out / ('previous-' + previous_live.name))
        if not (up / '.git').is_dir():
            up.mkdir(parents=True, exist_ok=True)
            sp.run(['git', 'init', '-q', str(up)], check=True)
            sp.run(['git', '-C', str(up), 'remote', 'add', 'origin', UPSTREAM_URL], check=True)
        sp.run(['git', '-C', str(up), 'fetch', '-q', '--depth=1', 'origin', '+refs/heads/cnb:refs/remotes/origin/cnb'], check=True)
        git(up, 'checkout', '-q', '--detach', 'origin/cnb')
        head = git(up, 'rev-parse', 'HEAD')
        before = git(M, 'rev-parse', 'HEAD')
        if git(M, 'show-ref', '--verify', '--quiet', 'refs/heads/klimt', check=False).returncode == 0:
            git(M, 'checkout', '-q', 'klimt')
        else:
            git(M, 'checkout', '-q', '-b', 'klimt')
        shutil.copyfile(up / 'default.xml', M / 'default.xml')
        if (M / 'snippets').is_dir():
            shutil.rmtree(M / 'snippets')  # tracked in .repo/manifests: a snippet upstream dropped shows as a deletion
        shutil.copytree(up / 'snippets', M / 'snippets')
        text, fixed = fix_github_fetch((M / 'default.xml').read_text())
        (M / 'default.xml').write_text(text)
        (M / LIVE).write_text(live)
        (S / '.repo/manifest.xml').write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<manifest>\n  <include name="{LIVE}" />\n</manifest>\n')
        git(M, 'add', '-A', 'default.xml', 'snippets', LIVE)
        if git(M, 'status', '--porcelain'):
            git(M, 'commit', '-q', '-m', f'{self.build}: track Evolution X manifest {head[:12]}')
        sp.run(['repo', 'manifest', '-o', str(self.out / 'upstream-live.xml')], cwd=S, check=True)
        print(self.record('upstream', dict(upstream_manifest=head, github_fetch_fixed=fixed, manifests_before=before,
              manifests_after=git(M, 'rev-parse', 'HEAD'), device_head=device, previous_live=str(previous_live),
              live_manifest_sha256=sha256(M / LIVE))))

    def move_renamed(self):
        self.require('move-renamed')
        self.on_klimt_branch()
        old = project_map(self.snapshot.read_text())
        new = project_map((self.out / 'upstream-live.xml').read_text())
        changed, added, removed = renamed_projects(old, new)
        remotes = sorted(p for p in old.keys() & new.keys() if p not in changed and old[p].get('remote') != new[p].get('remote'))
        print('renamed', changed, '\nadded', added, '\nremoved', removed, '\nremote changed (kept)', remotes)
        dest = paths.MOVED_PROJECTS / f'{self.build}-moved-projects'
        if self.dry:
            return
        if dest.exists() and any(dest.iterdir()):
            raise RuntimeError(str(dest) + ' is not empty')
        moves = []
        for p in changed:
            clean(S / p)
            for src, rel in [(S / '.repo/projects' / (p + '.git'), 'repo-projects/' + p + '.git'), (S / p, 'worktrees/' + p)]:
                if src.exists() or src.is_symlink():
                    target = dest / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(src), str(target))
                    moves.append(dict(project=p, old=old[p].get('name'), new=new[p].get('name'), src=str(src), dst=str(target)))
        print(self.record('move-renamed', dict(renamed=changed, added=added, removed=removed, remote_changed=remotes,
                                               moves=moves, destination=str(dest))))

    def sync(self):
        self.require('sync')
        self.on_klimt_branch()
        command = ['repo', 'sync', '-c', '--no-tags', '--no-clone-bundle', '--force-sync', '--no-manifest-update', '--detach', '-j8']
        if self.dry:
            print('would run in', S, ':', ' '.join(command))
            return
        log = self.out / 'sync.log'
        start = time.time()
        with open(log, 'a') as f:
            f.write(f'=== {time.strftime("%Y-%m-%dT%H:%M:%S%z")} {" ".join(command)}\n')
            f.flush()
            rc = sp.run(command, cwd=S, stdout=f, stderr=sp.STDOUT).returncode
        if rc:
            print(self.record('sync', dict(exit=rc, log=str(log), seconds=round(time.time() - start)), ok=False))
            raise SystemExit(f'repo sync failed ({rc}); see {log}')
        resolved = self.out / 'upstream-resolved.xml'
        sp.run(['repo', 'manifest', '-r', '-o', str(resolved)], cwd=S, check=True)
        changes = self.compare(project_map(self.snapshot.read_text()), project_map(resolved.read_text()))
        (self.out / 'UPSTREAM_CHANGES.json').write_text(json.dumps(changes, indent=2) + '\n')
        print(self.record('sync', dict(exit=0, log=str(log), seconds=round(time.time() - start), resolved=str(resolved),
              resolved_sha256=sha256(resolved), entries=len(changes), code_changed=sum(c['code_changed'] for c in changes))))

    def compare(self, old, new):
        changes = []
        for p in sorted(old.keys() | new.keys()):
            prev, curr = old.get(p), new.get(p)
            base, kind = comparison_base(p, prev)
            rev = (curr or {}).get('revision')
            if kind == 'fork' and rev:
                mb = git(S / p, 'merge-base', base, rev, check=False)
                base, kind = (mb.stdout.strip(), 'fork merge-base') if mb.returncode == 0 and mb.stdout.strip() else (base, 'fork pin (no merge base)')
            if base == rev and (prev or {}).get('name') == (curr or {}).get('name'):
                continue
            rec = dict(project=p, old_name=(prev or {}).get('name'), new_name=(curr or {}).get('name'),
                       comparison_base=base, base_kind=kind, new=rev, code_changed=base != rev)
            if base and rev and base != rev:
                stat = git(S / p, 'diff', '--shortstat', base, rev, check=False)
                rec['stat'] = stat.stdout.strip() if stat.returncode == 0 else 'diff-failed: ' + stat.stderr.strip()[-200:]
                names = git(S / p, 'diff', '--name-only', base, rev, check=False)
                rec['files'] = names.stdout.splitlines() if names.returncode == 0 else []
            changes.append(rec)
        return changes

    def synced_heads(self):
        """Project -> revision in this build's upstream-resolved.xml (what `sync` checked out)."""
        resolved = self.out / 'upstream-resolved.xml'
        return {p: a.get('revision') for p, a in project_map(resolved.read_text()).items()}

    def rebase_patches(self, bundle):
        """Evolution X rebases its projects often, which moves a patched project off its recorded base (apply.py
        says MISMATCH). For each such project whose HEAD is exactly what `sync` checked out, replay the recorded
        patches with `git am -3` on that head, re-export them with the device tree's export.py and commit the new
        PATCHES.json (and any patch files whose context changed) on the device tree's local cnb. A conflict stops
        the step with the project restored to its synced head: that patch needs a hand port. Returns the rebased
        projects ([] when nothing moved)."""
        apply_py = S / DEVICE / 'patches/apply.py'
        r = sp.run(['python3', '-B', str(apply_py), str(S), '--check'], capture_output=True, text=True)
        moved = [l.split()[1].rstrip(':') for l in r.stdout.splitlines() if l.startswith('MISMATCH ')]
        if not moved:
            return []
        synced = self.synced_heads()
        heads = {}
        for p in moved:
            head = git(S / p, 'rev-parse', 'HEAD')
            if synced.get(p) != head:
                raise SystemExit(f'{p}: HEAD {head} is not the synced revision {synced.get(p)}; not rebasing')
            heads[p] = head
        env = dict(os.environ, GIT_COMMITTER_NAME=COMMITTER[0], GIT_COMMITTER_EMAIL=COMMITTER[1])
        try:
            for p, head in heads.items():
                files = [str(S / DEVICE / 'patches' / f['file']) for f in bundle[p]['patches']]
                git(S / p, 'checkout', '-q', '-B', REBASE_BRANCH, head)
                # --keep-cr as apply.py (am.keepcr=true): some patched files are CRLF (SystemUI's charging files).
                am = sp.run(['git', '-C', str(S / p), 'am', '-3', '--keep-cr', '--committer-date-is-author-date', *files],
                            capture_output=True, text=True, env=env)
                if am.returncode:
                    sp.run(['git', '-C', str(S / p), 'am', '--abort'], capture_output=True)
                    raise SystemExit(f'{p}: the recorded patches do not apply on {head[:12]} even with a 3-way merge; '
                                     f'hand-port them, then run patches/export.py.\n{(am.stdout + am.stderr)[-1500:]}')
                print(f'REBASED {p}: {len(files)} patches on {head[:12]}')
            export = [sys.executable, '-B', str(S / DEVICE / 'patches/export.py'), str(S), *heads]
            for p, head in heads.items():
                export += ['--base', f'{p}={head}']
            ex = sp.run(export, capture_output=True, text=True)
            print(ex.stdout.strip())
            if ex.returncode:
                raise SystemExit('export.py failed; nothing committed\n' + ex.stderr.strip()[-1500:])
        finally:
            for p, head in heads.items():
                git(S / p, 'checkout', '-q', '--detach', head, check=False)
                git(S / p, 'branch', '-D', REBASE_BRANCH, check=False)
        g = S / DEVICE
        head = git(g, 'rev-parse', 'HEAD')
        git(g, 'checkout', '-q', '-B', 'cnb', head)
        git(g, 'add', '-A', 'patches')
        names = ', '.join(heads)
        msg = (f'klimt: patches: Rebase {names} for {self.build}\n\n'
               f'Evolution X moved {"these projects" if len(heads) > 1 else "this project"} since the recorded base. '
               'The patches applied with a 3-way merge\nand were re-exported by patches/export.py; their purpose is unchanged.\n\n'
               + ''.join(f'{p}: {bundle[p]["base"][:12]} -> {h[:12]}\n' for p, h in heads.items())
               + '\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n')
        sp.run(['git', '-C', str(g), '-c', f'user.name={COMMITTER[0]}', '-c', f'user.email={COMMITTER[1]}', 'commit', '-q', '-F', '-'],
               input=msg, text=True, check=True, env=env)
        print('device commit', git(g, 'rev-parse', 'HEAD'))
        return list(heads)

    def patch(self):
        self.require('patch')
        rebased = [] if self.dry else self.rebase_patches(self.bundle())
        bundle = self.bundle()
        apply_py = S / DEVICE / 'patches/apply.py'
        argv = ['python3', '-B', str(apply_py), str(S)] + (['--check'] if self.dry else [])
        r = sp.run(argv, capture_output=True, text=True)
        lines = [l.strip() for l in r.stdout.splitlines() if l.strip()]
        print('\n'.join(lines))
        if self.dry:
            return
        mismatch = [l for l in lines if l.startswith('MISMATCH')]
        for l in mismatch:
            print('re-export needed:', l.split(None, 1)[1] if ' ' in l else l, file=sys.stderr)
        check = sp.run(['python3', '-B', str(apply_py), str(S), '--check'], capture_output=True, text=True)
        final = [l.strip() for l in check.stdout.splitlines() if l.strip()]
        ok = r.returncode == 0 and check.returncode == 0 and not mismatch and final and all(l.startswith('FINAL') for l in final)
        rec = dict(rebased=rebased, apply_exit=r.returncode, apply_output=lines, apply_stderr=r.stderr.strip()[-2000:], check_exit=check.returncode,
                   check_output=final, projects=sorted(bundle), device_head=git(S / DEVICE, 'rev-parse', 'HEAD'),
                   heads={p: git(S / p, 'rev-parse', 'HEAD') for p in bundle})
        print(self.record('patch', rec, ok=bool(ok)))
        if not ok:
            raise SystemExit('Patches not applied; ' + ('re-export: ' + ', '.join(mismatch) if mismatch else 'see the record'))

    def label(self):
        self.require('label')
        g = S / DEVICE
        config = g / 'configs/kernel/metadata.config'
        text = config.read_text()
        new = relabel(text, self.previous, self.build)
        kernel = git(S / KERNEL, 'rev-parse', 'HEAD')
        if '-g' + kernel[:12] + '-' not in new:
            raise RuntimeError('metadata.config does not name the kernel HEAD ' + kernel[:12])
        if self.dry:
            print(new, end='')
            return
        head = git(g, 'rev-parse', 'HEAD')
        if git(g, 'show-ref', '--verify', '--quiet', 'refs/heads/cnb', check=False).returncode == 0:
            local = git(g, 'rev-parse', 'refs/heads/cnb')
            if git(g, 'merge-base', '--is-ancestor', local, head, check=False).returncode:
                raise RuntimeError(f'local cnb {local} is not part of the synced device HEAD {head}; check it by hand')
        git(g, 'checkout', '-q', '-B', 'cnb', head)
        config.write_text(new)
        git(g, 'add', 'configs/kernel/metadata.config')
        git(g, 'commit', '-q', '-m', f'klimt: label the {self.build} build (kernel -{paths.kernel_label(self.build)})')
        print(git(g, 'show', '--stat', '--format=%H %s', 'HEAD'))
        print(self.record('label', dict(device_before=head, device_after=git(g, 'rev-parse', 'HEAD'), kernel=kernel,
              label=paths.kernel_label(self.build), owner_push=f'git -C {g} push iowaz HEAD:refs/heads/cnb')))

    def freeze(self):
        import controller
        self.require('freeze')
        self.on_klimt_branch()
        bundle = self.bundle()
        resolved = self.out / ('final-resolved.dry-run.xml' if self.dry else 'final-resolved.xml')
        sp.run(['repo', 'manifest', '-r', '-o', str(resolved)], cwd=S, check=True)
        text = freeze_manifest(resolved.read_text(), bundle, self.build)
        frozen = controller.manifest_heads(text.encode())
        if controller.effective_heads(frozen, bundle) != controller.manifest_heads(resolved.read_bytes()):
            raise RuntimeError('Frozen pins plus PATCHES.json do not give the live heads')
        controller.live_heads(controller.effective_heads(frozen, bundle))
        debug = paths.for_build(self.build)['debug']
        out = debug / (f'{self.build}-frozen.dry-run.xml' if self.dry else f'{self.build}-frozen.xml')
        if self.dry:
            out.write_text(text)
            print(f'{len(frozen)} projects, {len(bundle)} pinned at their base; written {out}')
            return
        snapshot = paths.SNAPSHOTS / f'{self.build}.xml'
        if out.exists() or snapshot.exists() or (M / out.name).exists():
            raise RuntimeError('Frozen manifest already exists')
        with open(out, 'x', newline='\n') as f:
            f.write(text)
        shutil.copyfile(out, snapshot)
        shutil.copyfile(out, M / out.name)
        (S / '.repo/manifest.xml').write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<manifest>\n  <include name="{out.name}" />\n</manifest>\n')
        git(M, 'add', out.name)
        git(M, 'commit', '-q', '-m', f'{self.build}: freeze the synced sources ({len(bundle)} patched projects at their base)')
        print(self.record('freeze', dict(frozen=str(out), snapshot=str(snapshot), sha256=sha256(out), projects=len(frozen),
              patched={p: dict(base=r['base'], final_head=r['final_head']) for p, r in bundle.items()},
              device_head=frozen[DEVICE], manifests_head=git(M, 'rev-parse', 'HEAD'),
              owner_push=f'device/xiaomi/klimt {frozen[DEVICE]} to iowaz cnb (and the {self.build} tag after the build)')))

def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('step', choices=STEPS)
    ap.add_argument('build')
    ap.add_argument('--previous', help='the build whose snapshot the tree holds now (default: the newest snapshot before <build>)')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    if not paths.is_build(args.build) or (args.previous and not paths.is_build(args.previous)):
        ap.error('builds are YYYYMMDD or YYYYMMDD.N from 2026-11-04 (evoxNN only for history)')
    if os.environ.setdefault('KLIMT_BUILD', args.build) != args.build:
        ap.error('KLIMT_BUILD is ' + os.environ['KLIMT_BUILD'])
    prep = Prep(args.build, args.previous, args.dry_run)
    getattr(prep, args.step.replace('-', '_'))()

if __name__ == '__main__':
    main()
