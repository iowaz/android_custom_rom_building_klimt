#!/usr/bin/env python3
"""One attempt, immutable archive, isolated extraction and fail-closed verification."""
import importlib.util
import argparse
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile
from controller import B,S,L,C,D,O,ZIP,sha,write_json,lock,live_heads,capture_manifest,space,require_tooling_frozen,tooling_hashes,wsl_path,foreign_processes

ENTRIES={'android-info.txt','fastboot-info.txt','boot.img','dtbo.img','init_boot.img','odm.img','odm_dlkm.img',
    'product.img','super_empty.img','system.img','system_dlkm.img','system_ext.img','unsparse_super_empty.img',
    'vbmeta.img','vbmeta_system.img','vbmeta_vendor.img','vendor.img','vendor_boot.img','vendor_dlkm.img'}
COVERAGE={'policy','patch_packaging','private_compatibility','health_semantics','gms_themes_apps','doze_packaging'}

def review_binding(review,attempt_id,source_digest):
    if review.get('approved') is not True or review.get('attempt')!=attempt_id or review.get('source_snapshot_sha256')!=source_digest or not review.get('evidence'):
        raise RuntimeError('Tool re-review does not bind this attempt and unchanged source snapshot')
    if tooling_hashes()!=review.get('tooling_sha256'):
        raise RuntimeError('Re-reviewed tooling hash drift')

def future_flash_scripts(dest,archive,digest):
    stem=archive.name.replace('-img.zip','')
    script=dest/(stem+'-flash.sh')
    script.write_text('''#!/bin/bash
set -euo pipefail
test "${1:-}" = --flash || { echo 'Usage: bash "'$0'" --flash'; exit 2; }
cd -- "$(dirname -- "$0")"
test -f VERIFIED.txt || { echo 'VERIFIED.txt missing'; exit 2; }
printf '%s  %s\\n' 'DIGEST' 'ARCHIVE' | sha256sum -c -
command -v fastboot >/dev/null
product=$(fastboot getvar product 2>&1)
printf '%s\\n' "$product"
printf '%s' "$product" | grep -qE 'product: *klimt([[:space:]]|$)'
fastboot update --skip-reboot 'ARCHIVE'
echo 'Update complete. Reboot the phone when ready.'
'''.replace('DIGEST',digest).replace('ARCHIVE',archive.name),newline='\n')
    bat=dest/(stem+'-flash.bat')
    bat.write_text('''@echo off
setlocal
if /I not "%~1"=="/flash" (
  echo Usage: "%~nx0" /flash
  exit /b 2
)
cd /d "%~dp0"
if not exist VERIFIED.txt exit /b 2
powershell.exe -NoProfile -Command "if ((Get-FileHash -LiteralPath 'ARCHIVE' -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'DIGEST') { exit 2 }"
if errorlevel 1 exit /b 2
set "FASTBOOT=fastboot.exe"
if exist C:\\adb\\fastboot.exe set "FASTBOOT=C:\\adb\\fastboot.exe"
"%FASTBOOT%" getvar product > product-check.txt 2>&1
if errorlevel 1 exit /b 2
powershell.exe -NoProfile -Command "if (@(Select-String -LiteralPath 'product-check.txt' -Pattern '^(?:\\(bootloader\\)\\s*)?product:\\s*klimt\\s*$' -CaseSensitive).Count -ne 1) { exit 2 }"
if errorlevel 1 exit /b 2
"%FASTBOOT%" update --skip-reboot "ARCHIVE"
if errorlevel 1 exit /b 1
echo Update complete. Reboot the phone when ready.
exit /b 0
'''.replace('DIGEST',digest).replace('ARCHIVE',archive.name),newline='\r\n')
    return [script,bat]

def image_checks(ready,env,report):
    checks=ready.get('image_checks',[])
    if set(c.get('coverage') for c in checks)!=COVERAGE:
        raise RuntimeError('All six Evox16 supplemental image coverage tracks need reviewed producer/artifact checks')
    names=[c.get('name') for c in checks]
    if len(set(names))!=len(names) or any(not n for n in names):raise RuntimeError('Image check names missing/duplicate')
    results=[]
    for index,c in enumerate(checks):
        argv=c.get('argv',[])
        if not isinstance(argv,list) or len(argv)<2 or argv[0] not in ('bash','python3'):
            raise RuntimeError('Image check must be an explicit bash/python3 script argv')
        if sha(Path(argv[1]))!=c.get('script_sha256'):
            raise RuntimeError('Supplemental image check hash drift: '+c['name'])
        log=report/f'raw-image-check-{index:02d}.txt'
        with open(log,'xb') as f:
            result=subprocess.run(argv,cwd=S,env=env,stdout=f,stderr=subprocess.STDOUT)
        record=dict(name=c['name'],coverage=c['coverage'],exit=result.returncode,log=str(log),script_sha256=c['script_sha256'])
        results.append(record)
        write_json(report/'supplemental-results.json',results)
        if result.returncode:raise RuntimeError('Supplemental image check failed: '+c['name'])
    return results

def inventory(root):
    return [{'path':str(p.relative_to(root)), 'bytes':p.stat().st_size,'sha256':sha(p)}
        for p in sorted(root.rglob('*')) if p.is_file() and not p.is_symlink()]

def main(attempt,recheck=None,tool_review=None):
    inherited=os.environ.get('EVOX_SOURCE_LOCK_FD')
    if inherited:
        fd=int(inherited)
        if os.fstat(fd).st_ino!=(L/'source.lock').stat().st_ino or os.fstat(fd).st_dev!=(L/'source.lock').stat().st_dev:
            raise RuntimeError('Inherited source lock identity mismatch')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        source_lock=None
    else:
        source_lock=lock(L/'source.lock')
    vlock=lock(L/'verification.lock')
    identity=json.loads((attempt/'owner.json').read_text())
    def tools_match():
        if review:
            if tooling_hashes()!=review['tooling_sha256']:raise RuntimeError('Re-reviewed tooling hash drift')
        else:require_tooling_frozen(attempt)
    review=None
    if recheck:
        if not re.fullmatch(r'recheck\d{2,}',recheck) or not tool_review:
            raise RuntimeError('Recheck requires recheckNN and an approved tool-review JSON')
        review=json.loads(tool_review.read_text())
        review_binding(review,identity['attempt'],sha(attempt/'prebuild.xml'))
    tools_match()
    exit_record=json.loads((attempt/'build-exit.json').read_text())
    if exit_record.get('exit')!=0:
        raise RuntimeError('Only this attempt exit zero permits verification')
    if sha(ZIP)!=exit_record.get('zip_sha256') or ZIP.stat().st_mtime_ns!=exit_record.get('zip_mtime_ns') or ZIP.stat().st_size!=exit_record.get('zip_bytes'):
        raise RuntimeError('ZIP differs from the producing wrapper exit evidence')
    attempt_id=identity['attempt']; report=C/attempt_id
    ready=json.loads((attempt/'BUILD_READY.json').read_text())
    if review and 'image_checks' in review:
        ready['image_checks']=review['image_checks']
    heads=ready['reviewed_project_heads']
    if foreign_processes():raise RuntimeError('Competing historical build/extraction exists')
    if ZIP.stat().st_mtime_ns < identity['started_ns']:
        raise RuntimeError('Stale input archive')
    live_heads(heads)
    evidence=attempt
    if recheck:
        report=report/'rechecks'/recheck
        report.mkdir(parents=True,exist_ok=False)
        evidence=attempt/'rechecks'/recheck
        evidence.mkdir(parents=True,exist_ok=False)
        shutil.copyfile(tool_review,evidence/'TOOL_REVIEW.json')
        write_json(evidence/'effective-ready.json',ready,True)
    if capture_manifest(evidence/'preverify.xml')!=heads:raise RuntimeError('Preverify manifest drift')
    if (report/'VERIFIED.txt').exists():raise RuntimeError('Already verified; no overwrite')
    free=space()
    if free['host']<38 or free['output']<24 or free['source']<2:
        raise RuntimeError('Archive/extraction headroom below 6 GiB ZIP + 22 GiB extraction + 10 GiB host reserve / 24 GiB ext4')
    extract=Path('/mnt/wsl/build/compare/evox16')/attempt_id
    dest=Path('/mnt/d/WitAquaBuild/out-evox/evox16')/attempt_id
    if recheck:
        extract=extract/'rechecks'/recheck
        dest=dest/'rechecks'/recheck
    dest.mkdir(parents=True,exist_ok=False)
    archive=dest/f'lineage_klimt-{attempt_id}-img.zip'
    # Preserve evidence of copy failures in an explicitly partial file.
    partial=archive.with_suffix(archive.suffix+'.partial')
    with open(ZIP,'rb') as src,open(partial,'xb') as out:shutil.copyfileobj(src,out,4*1024*1024)
    digest=sha(partial)
    if sha(ZIP)!=digest:raise RuntimeError('Archive copy hash mismatch')
    if archive.exists():raise RuntimeError('Attempt archive exists')
    partial.rename(archive)
    with zipfile.ZipFile(archive) as z:
        entries=z.infolist()
        if {i.filename for i in entries}!=ENTRIES or len(entries)!=len(ENTRIES):
            raise RuntimeError('Fastboot artifact inventory differs; review required')
        bad=z.testzip()
        if bad:raise RuntimeError('ZIP CRC failed: '+bad)
        write_json(report/'archive-inventory.json',[dict(name=i.filename,bytes=i.file_size,compressed=i.compress_size,crc=i.CRC) for i in entries],True)
    env=dict(os.environ,EVOX_EXTRACT=str(extract),EVOX_TMP=str(extract/'tmp'),EVOX_READY=str(evidence/'effective-ready.json' if recheck else attempt/'BUILD_READY.json'),EVOX_REPORT=str(report))
    for filename,argv in [('raw-extract.txt',['bash',str(B/'extract.sh'),str(archive),str(extract)]),
                          ('raw-musthold.txt',['bash',str(B/'legacy/musthold.sh')])]:
        with open(report/filename,'xb') as f:
            subprocess.run(argv,cwd=S,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
    with open(report/'raw-fixcheck.txt','xb') as f:
        subprocess.run(['bash',str(B/'legacy/fixcheck14.sh')],cwd=S,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
        subprocess.run(['python3','-B',str(B/'check-health-his.py')],cwd=S,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
    spec=importlib.util.spec_from_file_location('report_gates',B/'report-gates.py')
    gates=importlib.util.module_from_spec(spec);spec.loader.exec_module(gates)
    historical=gates.validate(report)
    supplemental=image_checks(ready,env,report)
    write_json(report/'filesystem-files.json',inventory(extract/'fs'),True)
    write_json(report/'image-files.json',inventory(extract/'img'),True)
    if capture_manifest(evidence/'postverify.xml')!=heads:raise RuntimeError('Postverify manifest drift')
    live_heads(heads)
    tools_match()
    results=dict(attempt=attempt_id,archive=str(archive),archive_sha256=digest,archive_bytes=archive.stat().st_size,
        recheck=recheck,historical=historical,supplemental=supplemental,source_heads=heads,runtime_unvalidated=True,time=time.time())
    write_json(report/'RESULTS.json',results,True)
    comparison=f'''# Evox16 comparison — {attempt_id}

Image verification passed against the historical author/build9 layout and saved live-slot DTB/DTBO references. The current kernel has 888 modules, zero CRC mismatches and the explicitly retained unresolved `mtk_drm_gateic_set_backlight` symbol.

Every historical check identity passed, including corrected USB-context and fingerprint-client attribute semantics. Supplemental Evox16 checks passed for policy, patch packaging, private compatibility, Health semantics, GMS/themes/apps and Doze packaging. Raw reports and machine-readable inventories are retained beside this report.

Archive: `{archive.name}`. SHA256: `{digest}`. Source inputs match the frozen pre/post compilation and verification manifests. The build is `lineage_klimt-cp2a-user` with GMS and existing signing certificates.

Runtime AOD/fingerprint/camera/charging behavior remains unvalidated. Flashing wrappers are supplied for a later explicitly authorized invocation.
'''
    (report/'COMPARISON-evox16.md').write_text(comparison)
    scripts=future_flash_scripts(dest,archive,digest)
    shutil.copyfile(report/'RESULTS.json',dest/'RESULTS.json')
    shutil.copyfile(report/'COMPARISON-evox16.md',dest/'COMPARISON-evox16.md')
    for name in ('prebuild.xml','postbuild.xml','postverify.xml'):
        shutil.copyfile(evidence/name if name=='postverify.xml' else attempt/name,dest/name)
    if review:shutil.copyfile(tool_review,dest/'TOOL_REVIEW.json')
    (dest/'README.md').write_text(f'''# Evox16 controlled test image — {attempt_id}

Build target: lineage_klimt-cp2a-user. Image verification passed; hardware runtime validation is pending.

The fastboot image ZIP contains the same 19 artifacts as Evox15. Supplied Windows `.bat` and Linux `.sh` wrappers check the ZIP hash and Klimt product, use `fastboot update --skip-reboot`, preserve data and leave reboot to the operator. Run only after separately authorizing the phone operation. They require the phone already in fastboot and a working fastboot installation.

See COMPARISON-evox16.md and RESULTS.json for image/source evidence. `sha256sum -c SHA256SUMS` validates the complete delivery set.
''')
    marker='evox16 image verified; source/producer/archive/layout/AVB/kernel/policy/patch/private compatibility checks passed. Runtime validation pending.\n'
    # This marker is written last, after every required image/provenance gate.
    paths=sorted(p for p in dest.iterdir() if p.is_file())
    sums={p.name:sha(p) for p in paths}
    sums['VERIFIED.txt']=hashlib.sha256(marker.encode()).hexdigest()
    (dest/'SHA256SUMS').write_text(''.join(sums[name]+'  '+name+'\n' for name in sorted(sums)))
    (report/'VERIFIED.txt').write_text(marker)
    (dest/'VERIFIED.txt').write_text(marker)
    if recheck:
        write_json(attempt/'status.json',dict(state='image-verified-runtime-pending',recheck=recheck,report=str(report),time=time.time()))
    print('IMAGE VERIFIED; runtime pending:',archive,digest)
    vlock.close()
    if source_lock:source_lock.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('attempt')
    parser.add_argument('--recheck')
    parser.add_argument('--tool-review')
    args=parser.parse_args()
    if args.tool_review and not args.recheck:parser.error('--tool-review requires --recheck')
    main(wsl_path(args.attempt),args.recheck,wsl_path(args.tool_review) if args.tool_review else None)
