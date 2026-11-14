"""Prepare 20261113.2 from 20261113 plus the reviewed keybox revision pair."""
from pathlib import Path
import contextlib, json, os, shutil, subprocess, sys, time
BASE=Path('/mnt/d/android_rom_building')
PIPE=BASE/'repositories/android_custom_rom_building_klimt/build-setup/evox/pipeline'
os.environ['KLIMT_BUILD']='20261113.2'
sys.path.insert(0,str(PIPE))
import controller, paths, prepare, candidate_gates, local_rom_control
BUILD='20261113.2'; CONTROL='20261113'
ROOT=paths.SRC; DEVICE=ROOT/'device/xiaomi/klimt'; MANIFESTS=ROOT/'.repo/manifests'
DIAG=paths.for_build(BUILD)['debug']; PREP=DIAG/'preparation'
SNAP=paths.SNAPSHOTS/(BUILD+'.xml')
BASELINE=paths.SNAPSHOTS/(CONTROL+'.xml')
REVIEW=BASE/'diagnostics/features/keybox-monitor/20261113.2/IMPLEMENTATION.json'
def git(repo,*args):
    return subprocess.check_output(['git','-C',str(repo),*args],text=True).strip()
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as stream: json.dump(value,stream,indent=2);stream.write('\n')

if SNAP.exists() or (PREP/'CANDIDATE.json').exists(): raise RuntimeError('Build already prepared')
with contextlib.ExitStack() as stack:
    for directory in sorted(set(paths.LOGS.glob('*'))|{paths.for_build(BUILD)['logs']}):
        if paths.is_build(directory.name): stack.enter_context(controller.lock(directory/'source.lock'))
    if controller.foreign_processes(): raise RuntimeError('A build/extraction is active')
    if git(MANIFESTS,'status','--porcelain'): raise RuntimeError('Manifests dirty')
    if git(MANIFESTS,'branch','--show-current')!='klimt': raise RuntimeError('Unexpected manifest branch')
    if git(DEVICE,'branch','--show-current')!='cnb': raise RuntimeError('Unexpected device branch')
    changed=subprocess.check_output(['git','-C',str(DEVICE),'status','--porcelain'],text=True).splitlines()
    if any(not line[3:].startswith('patches/') for line in changed): raise RuntimeError('Unrelated device edits')
    old_raw=controller.manifest_heads(BASELINE.read_bytes())
    old_bundle=controller.patch_bundle(old_raw)
    old=controller.effective_heads(old_raw,old_bundle)
    before_device=git(DEVICE,'rev-parse','HEAD')
    if before_device!=old[controller.DEVICE]: raise RuntimeError('Unexpected starting device HEAD')
    new_bundle=controller.parse_patch_bundle((DEVICE/'patches/PATCHES.json').read_text())
    reviewed=json.loads(REVIEW.read_text())
    expected=dict(old,**reviewed['source_heads'])
    expected[controller.DEVICE]=before_device
    controller.live_heads({p:h for p,h in expected.items() if p!=controller.DEVICE})
    # Check the bundle extension before committing the device metadata/patches.
    compared=dict(expected);compared[controller.DEVICE]='pending-device-commit'
    local_rom_control.check_delta(old,compared,old_bundle,new_bundle,reviewed['source_heads'])
    metadata=DEVICE/'configs/kernel/metadata.config'
    labelled=prepare.relabel(metadata.read_text(),CONTROL,BUILD)
    check=subprocess.run(['python3',str(DEVICE/'patches/apply.py'),str(ROOT),'--check'],capture_output=True,text=True)
    if check.returncode: raise RuntimeError(check.stdout+check.stderr)
    PREP.mkdir(parents=True,exist_ok=True)
    write(PREP/'BEFORE.json',dict(build=BUILD,control=CONTROL,device_before=before_device,
          manifests_before=git(MANIFESTS,'rev-parse','HEAD'),implementation_review=candidate_gates.file_record(REVIEW)))
    shutil.copyfile(ROOT/'.repo/manifest.xml',PREP/'manifest-wrapper-before.xml')
    metadata.write_text(labelled)
    subprocess.run(['git','-C',str(DEVICE),'add','patches','configs/kernel/metadata.config'],check=True)
    subprocess.run(['git','-C',str(DEVICE),'-c','commit.gpgSign=false','commit','-m',
                    'klimt: refine scheduled keybox monitoring and label the 20261113.2 build'],check=True)
    device_head=git(DEVICE,'rev-parse','HEAD')
    expected[controller.DEVICE]=device_head
    controller.live_heads(expected)
    resolved=PREP/'final-resolved.xml'
    subprocess.run(['repo','manifest','-r','-o',str(resolved)],cwd=ROOT,check=True)
    frozen_text=prepare.freeze_manifest(resolved.read_text(),new_bundle,BUILD)
    frozen=controller.manifest_heads(frozen_text.encode())
    if controller.effective_heads(frozen,new_bundle)!=expected: raise RuntimeError('Resolved graph differs')
    snapshot=DIAG/(BUILD+'-frozen.xml')
    with snapshot.open('x') as stream:stream.write(frozen_text)
    shutil.copyfile(snapshot,SNAP)
    shutil.copyfile(snapshot,MANIFESTS/snapshot.name)
    (ROOT/'.repo/manifest.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<manifest>\n  <include name="'+snapshot.name+'" />\n</manifest>\n')
    subprocess.run(['git','-C',str(MANIFESTS),'add',snapshot.name],check=True)
    subprocess.run(['git','-C',str(MANIFESTS),'-c','commit.gpgSign=false','commit','-m',
                    BUILD+': freeze reviewed local keybox patches on '+CONTROL],check=True)
    proof=PREP/'LOCAL_ROM_REVIEW.json'
    write(proof,dict(schema=1,mode=local_rom_control.MODE,build=BUILD,control_build=CONTROL,
        effective_control_heads=old,effective_candidate_heads=expected,
        patch_check_exit=check.returncode,patch_check_output=check.stdout.splitlines(),
        implementation_review=candidate_gates.file_record(REVIEW),
        preparation_script=candidate_gates.file_record(Path(__file__)),
        prior_patches_preserved=True,upstream_sync_performed=False))
    anchor=json.loads((paths.for_build(CONTROL)['preparation']/'CANDIDATE.json').read_text())
    record=dict(schema=1,mode=local_rom_control.MODE,build=BUILD,control_build=CONTROL,
        baseline=str(BASELINE),baseline_sha256=controller.sha(BASELINE),
        frozen_sha256=controller.sha(snapshot),
        heads={p:frozen[p] for p in (controller.DEVICE,'kernel/xiaomi/klimt')},
        control_freeze_utc=anchor['control_freeze_utc'],tooling_sha256=controller.tooling_hashes(),
        implementation_review=candidate_gates.file_record(REVIEW),
        preparation_review=candidate_gates.file_record(proof),published=False)
    candidate_gates.freeze_deadline(record)
    local_rom_control.validate(record,frozen,controller.sha(snapshot),controller.tooling_hashes())
    write(PREP/'CANDIDATE.json',record)
    write(PREP/'LABEL.json',dict(ok=True,step='label',build=BUILD,previous=CONTROL,
        device_before=before_device,device_after=device_head,kernel=frozen['kernel/xiaomi/klimt'],label='ab'+BUILD))
    write(PREP/'FREEZE.json',dict(ok=True,step='freeze',build=BUILD,previous=CONTROL,
        frozen=str(snapshot),snapshot=str(SNAP),sha256=controller.sha(snapshot),projects=len(frozen),device_head=device_head))
    print('PREPARED',BUILD,'projects',len(frozen),'patches',sum(len(r['patches']) for r in new_bundle.values()),flush=True)
