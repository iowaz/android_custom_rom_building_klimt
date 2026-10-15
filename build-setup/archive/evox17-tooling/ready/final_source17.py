"""Record the frozen evox17 source: every live HEAD equals evox17-frozen.xml and every worktree is clean."""
import json, sys, time, subprocess
from pathlib import Path
sys.path.insert(0, '/mnt/c/XiaomiBuilds/build-setup/evox/evox17')
from controller import manifest_heads, live_heads, sha, S
D = Path('/mnt/c/XiaomiBuilds/debug/evox17')
snap = D / 'evox17-frozen.xml'
active = S / '.repo/manifests/evox17-frozen.xml'
assert sha(snap) == sha(active), 'active repo manifest differs from the recorded snapshot'
heads = manifest_heads(snap.read_bytes())
live_heads(heads)  # raises on any HEAD drift or dirty/untracked project
excluded = {p: heads[p] for p in ['kernel/xiaomi/klimt', 'kernel/xiaomi/klimt-prebuilt', 'vendor/xiaomi/klimt', 'hardware/xiaomi', 'device/mediatek/sepolicy_vndr']}
old = json.loads(Path('/mnt/c/XiaomiBuilds/debug/evox16/FINAL_SOURCE.json').read_text())
same_excluded = {p: (old['excluded_heads'].get(p), v) for p, v in excluded.items()}
certs = {n: sha(S / 'vendor/evolution-priv/keys' / f'{n}.x509.pem') for n in ['platform', 'releasekey', 'shared', 'media', 'networkstack']}
assert certs == old['public_certificate_sha256'], 'signing certificates changed since evox16'
rec = dict(pass_=True, snapshot=str(snap), snapshot_sha256=sha(snap), projects=len(heads), heads=heads,
           excluded_heads=excluded, excluded_vs_evox16=same_excluded, public_certificate_sha256=certs,
           all_worktrees_clean=True, manifest_repository_commit='c6347cc7355b2e1e025e3c9738656811f7196c62', time=time.time())
rec['pass'] = rec.pop('pass_')
(D / 'FINAL_SOURCE.json').write_text(json.dumps(rec, indent=1) + '\n')
print('FINAL_SOURCE written:', len(heads), 'projects; snapshot', rec['snapshot_sha256'][:12])
for p, (a, b) in same_excluded.items(): print(f'  excluded {p}: evox16 {str(a)[:10]} -> evox17 {b[:10]}')
