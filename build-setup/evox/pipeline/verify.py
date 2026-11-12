#!/usr/bin/env python3
"""One attempt, immutable archive, isolated extraction and fail-closed verification.

The sealed readiness record `verification` selects the mode (verification.py): `simple` runs simple_main();
a readiness without the record, or with mode `full`, runs the established full verifier below.
Exit 0 passed; 1 artifact/assertion defect; 2 missing tool/evidence or wrong host; 3 unexpected error; 130 interrupt.
"""
import hostcheck
hostcheck.require_linux(__file__)
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
import paths
import verification
from verification import Defect, Missing
from controller import B,S,L,C,D,O,X,ZIP,BUILD,GIB,sha,write_json,lock,live_heads,ready_heads,capture_manifest,space,require_tooling_frozen,tooling_hashes,wsl_path,foreign_processes

ENTRIES={'android-info.txt','fastboot-info.txt','boot.img','dtbo.img','init_boot.img','odm.img','odm_dlkm.img',
    'product.img','super_empty.img','system.img','system_dlkm.img','system_ext.img','unsparse_super_empty.img',
    'vbmeta.img','vbmeta_system.img','vbmeta_vendor.img','vendor.img','vendor_boot.img','vendor_dlkm.img'}
COVERAGE={'policy','patch_packaging','private_compatibility','health_semantics','gms_themes_apps','doze_packaging','install_integrity'}

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
test "$(printf '%s\\n' "$product" | grep -cE '^(\\(bootloader\\)[[:space:]]*)?product:[[:space:]]*klimt[[:space:]]*$')" = 1
fastboot --slot=b update --skip-reboot 'ARCHIVE'
fastboot reboot
echo 'Update complete. Android reboot requested.'
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
if exist "%~dp0..\\..\\tools\\platform-tools\\fastboot.exe" set "FASTBOOT=%~dp0..\\..\\tools\\platform-tools\\fastboot.exe"
"%FASTBOOT%" getvar product > product-check.txt 2>&1
if errorlevel 1 exit /b 2
powershell.exe -NoProfile -Command "if (@(Select-String -LiteralPath 'product-check.txt' -Pattern '^(?:\\(bootloader\\)\\s*)?product:\\s*klimt\\s*$' -CaseSensitive).Count -ne 1) { exit 2 }"
if errorlevel 1 exit /b 2
"%FASTBOOT%" --slot=b update --skip-reboot "ARCHIVE"
if not "%errorlevel%"=="0" exit /b 1
"%FASTBOOT%" reboot
if not "%errorlevel%"=="0" exit /b 1
echo Update complete. Android reboot requested.
exit /b 0
'''.replace('DIGEST',digest).replace('ARCHIVE',archive.name),newline='\r\n')
    return [script,bat]

def run_tracks(checks,env,report,coverages,start=0):
    """Run registered supplemental image checks (image-checks/IMAGE_CHECKS.json) for the given coverages."""
    names=[c.get('name') for c in checks]
    if len(set(names))!=len(names) or any(not n for n in names):raise RuntimeError('Image check names missing/duplicate')
    results=[]
    for index,c in enumerate(checks):
        if c.get('coverage') not in coverages:continue
        argv=c.get('argv',[])
        if not isinstance(argv,list) or len(argv)<2 or argv[0] not in ('bash','python3'):
            raise RuntimeError('Image check must be an explicit bash/python3 script argv')
        if sha(Path(argv[1]))!=c.get('script_sha256'):
            raise RuntimeError('Supplemental image check hash drift: '+c['name'])
        log=report/f'raw-image-check-{start+index:02d}.txt'
        with open(log,'xb') as f:
            result=subprocess.run(argv,cwd=S,env=env,stdout=f,stderr=subprocess.STDOUT)
        record=dict(name=c['name'],coverage=c['coverage'],exit=result.returncode,log=str(log),script_sha256=c['script_sha256'])
        results.append(record)
        write_json(report/'supplemental-results.json',results)
        if result.returncode==1:raise Defect('Supplemental image check failed: '+c['name'],'track.'+c['coverage'])
        if result.returncode:raise Missing('Supplemental image check could not run (exit %d): %s'%(result.returncode,c['name']),'track.'+c['coverage'])
    return results

def image_checks(ready,env,report):
    checks=ready.get('image_checks',[])
    if set(c.get('coverage') for c in checks)!=COVERAGE:
        raise RuntimeError('All seven supplemental image coverage tracks need reviewed producer/artifact checks')
    return run_tracks(checks,env,report,COVERAGE)

def inventory(root):
    return [{'path':str(p.relative_to(root)), 'bytes':p.stat().st_size,'sha256':sha(p)}
        for p in sorted(root.rglob('*')) if p.is_file() and not p.is_symlink()]

def effective_readiness(attempt,review):
    ready=json.loads((attempt/'BUILD_READY.json').read_text())
    if review:
        import reviewed_readiness, candidate_gates
        ready = reviewed_readiness.apply(ready, review, candidate_gates.revalidate, candidate_gates.validate_ready)
    elif ready.get('candidate_evidence'):
        import release_audit
        ready = release_audit.effective_ready(attempt, ready)
    return ready

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
    ready=effective_readiness(attempt,review)
    if verification.mode_of(ready)=='simple':
        simple_main(attempt,identity,review,recheck,tool_review,exit_record,ready,tools_match)
        vlock.close()
        if source_lock:source_lock.close()
        return
    if sha(ZIP)!=exit_record.get('zip_sha256') or ZIP.stat().st_mtime_ns!=exit_record.get('zip_mtime_ns') or ZIP.stat().st_size!=exit_record.get('zip_bytes'):
        raise RuntimeError('ZIP differs from the producing wrapper exit evidence')
    attempt_id=identity['attempt']; report=C/attempt_id
    heads=ready_heads(ready)  # frozen pins, patched projects at their PATCHES.json final_head
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
    elif ready.get('candidate_evidence'):
        write_json(evidence/'effective-ready.json',ready,True)
    if capture_manifest(evidence/'preverify.xml')!=heads:raise RuntimeError('Preverify manifest drift')
    if (report/'VERIFIED.txt').exists():raise RuntimeError('Already verified; no overwrite')
    free=space()
    if free['host']<38 or free['output']<24 or free['source']<2:
        raise RuntimeError('Archive/extraction headroom below 6 GiB ZIP + 22 GiB extraction + 10 GiB host reserve / 24 GiB ext4')
    extract=X/attempt_id
    # Staged on Windows next to the reports; promote.py moves the chosen delivery to output-zips/<build>.
    dest=paths.for_build(BUILD)['staging']/attempt_id
    if recheck:
        extract=extract/'rechecks'/recheck
        dest=dest/'rechecks'/recheck
    dest.mkdir(parents=True,exist_ok=False)
    archive=dest/f'lineage_klimt-{BUILD}-img.zip'
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
            raise Defect('Fastboot artifact inventory differs; review required')
        bad=z.testzip()
        if bad:raise Defect('ZIP CRC failed: '+bad)
        write_json(report/'archive-inventory.json',[dict(name=i.filename,bytes=i.file_size,compressed=i.compress_size,crc=i.CRC) for i in entries],True)
    env=dict(os.environ,KLIMT_BUILD=BUILD,EVOX_EXTRACT=str(extract),EVOX_TMP=str(extract/'tmp'),EVOX_READY=str(evidence/'effective-ready.json' if recheck or ready.get('candidate_evidence') else attempt/'BUILD_READY.json'),EVOX_REPORT=str(report))
    if ready.get('candidate_evidence'):
        import kernel_artifact, candidate_gates
        audit = candidate_gates.revalidate(ready['candidate_evidence']['kernel_audit'])
        env['EVOX_KERNEL_SYMVERS'] = str(kernel_artifact.audited_symvers(audit))
    for filename,argv in [('raw-extract.txt',['bash',str(B/'extract.sh'),str(archive),str(extract)]),
                          ('raw-musthold.txt',['bash',str(B/'legacy/musthold.sh')])]:
        with open(report/filename,'xb') as f:
            subprocess.run(argv,cwd=S,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
    with open(report/'raw-fixcheck.txt','xb') as f:
        subprocess.run(['bash',str(B/'legacy/fixcheck21.sh')],cwd=S,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
        subprocess.run(['python3','-B',str(B/'check-health-his.py')],cwd=S,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
    spec=importlib.util.spec_from_file_location('report_gates',B/'report-gates.py')
    gates=importlib.util.module_from_spec(spec);spec.loader.exec_module(gates)
    historical=gates.validate(report,BUILD,ready.get('kernel_expectation'))
    if paths.at_least(BUILD,26):
        subprocess.run(['python3','-B',str(B/'check-metadata26.py')],cwd=S,env=env,check=True)
    supplemental=image_checks(ready,env,report)
    if ready.get('candidate_evidence'):
        import candidate_gates, rollback_security
        candidate_gates.validate_ready(ready, ready['reviewed_project_heads'])
        audit = candidate_gates.revalidate(ready['candidate_evidence']['kernel_audit'])
        import kernel_artifact
        binding = kernel_artifact.validate(audit, ready['reviewed_project_heads'], extract/'img/boot.img',
                                           extract/'fs/system_dlkm', digest, S)
        write_json(report/'kernel-artifact-binding.json', binding, True)
        baseline = candidate_gates.revalidate(ready['candidate_evidence']['rollback_baseline'])['security']
        security = rollback_security.collect(extract, S/'external/avb/avbtool.py', ready['security']['platform_security_patch'])
        write_json(report/'rollback-security-candidate.json', security, True)
        write_json(report/'rollback-security-equality.json', rollback_security.compare(baseline, security), True)
    write_json(report/'filesystem-files.json',inventory(extract/'fs'),True)
    write_json(report/'image-files.json',inventory(extract/'img'),True)
    if capture_manifest(evidence/'postverify.xml')!=heads:raise RuntimeError('Postverify manifest drift')
    live_heads(heads)
    tools_match()
    results=dict(attempt=attempt_id,archive=str(archive),archive_sha256=digest,archive_bytes=archive.stat().st_size,
        recheck=recheck,historical=historical,supplemental=supplemental,source_heads=heads,runtime_unvalidated=True,time=time.time())
    if ready.get('candidate_evidence'):
        results['candidate_evidence'] = ready['candidate_evidence']
        results['kernel_expectation'] = ready['kernel_expectation']
        results['kernel_artifact_evidence'] = {name: sha(report/name) for name in
                                               ('kernel-artifact-binding.json', 'image-files.json', 'filesystem-files.json')}
        results['rollback_security'] = {name: sha(report/name) for name in
                                       ('rollback-security-candidate.json', 'rollback-security-equality.json')}
    write_json(report/'RESULTS.json',results,True)
    comparison=f'''# {BUILD} comparison — {attempt_id}

Static image checks passed against the historical author/build9 layout and saved live-slot DTB/DTBO references. The current kernel has 888 modules, zero CRC mismatches and the explicitly retained unresolved `mtk_drm_gateic_set_backlight` symbol.

Every historical check identity passed, including corrected USB-context and fingerprint-client attribute semantics. Supplemental checks passed for policy, patch packaging, private compatibility, Health semantics, GMS/themes/apps, Doze packaging and install integrity (every staged file is a product install, no package identity twice, Telecom app variant matches the framework loader). Raw reports and machine-readable inventories are retained beside this report.

Archive: `{archive.name}`. SHA256: `{digest}`. Source inputs match the frozen pre/post compilation and verification manifests. The build is `lineage_klimt-cp2a-user` with GMS and existing signing certificates.

**Not boot-tested.** These are static checks of files and producers; evox16 passed the same kind of checks and boot-looped. Boot, AOD, fingerprint, camera and charging remain unvalidated until the phone runs it. Flashing wrappers are supplied for a later explicitly authorized invocation.
'''
    (report/'COMPARISON.md').write_text(comparison)
    scripts=future_flash_scripts(dest,archive,digest)
    shutil.copyfile(report/'RESULTS.json',dest/'RESULTS.json')
    shutil.copyfile(report/'COMPARISON.md',dest/'COMPARISON.md')
    for name in dict(results.get('rollback_security', {}), **results.get('kernel_artifact_evidence', {})):
        shutil.copyfile(report/name, dest/name)
    for name in ('prebuild.xml','postbuild.xml','postverify.xml'):
        shutil.copyfile(evidence/name if name=='postverify.xml' else attempt/name,dest/name)
    if review:shutil.copyfile(tool_review,dest/'TOOL_REVIEW.json')
    (dest/'README.md').write_text(f'''# {BUILD} image — {attempt_id}

Build target: lineage_klimt-cp2a-user. Static image checks passed. **Not boot-tested**. Keep the previous boot-tested ZIP available. Rollback to an older vendor security patch level is unvalidated.

The fastboot image ZIP contains the same 19 artifacts as Evox15. Supplied Windows `.bat` and Linux `.sh` wrappers check the ZIP hash and Klimt product, select slot b with `fastboot --slot=b update --skip-reboot`, omit data wiping and run `fastboot reboot` only after a successful update. Failed flashes remain in fastboot. Run only after authorizing the flash; that authorization includes the successful-flash reboot unless the owner explicitly asks to stay in fastboot. They require the phone already in fastboot and a working fastboot installation.

The update writes slot b and selects it as active. In Windows run `{scripts[1].name} /flash`; in Linux run `bash ./{scripts[0].name} --flash`. These commands are supplied for the operator; package preparation does not run them.

See COMPARISON.md and RESULTS.json for image/source evidence. `sha256sum -c SHA256SUMS` validates the complete delivery set.
''')
    marker=BUILD+' static image checks passed (source/producer/archive/layout/AVB/kernel/policy/patch/private compatibility/install integrity). NOT boot-tested.\n'
    if ready.get('candidate_evidence'):
        (dest/'RUNTIME_PENDING.md').write_text(RUNTIME_PENDING)
    # This marker is written last, after every required image/provenance gate.
    files=sorted(p for p in dest.iterdir() if p.is_file())
    sums={p.name:sha(p) for p in files}
    sums['VERIFIED.txt']=hashlib.sha256(marker.encode()).hexdigest()
    (dest/'SHA256SUMS').write_text(''.join(sums[name]+'  '+name+'\n' for name in sorted(sums)))
    (report/'VERIFIED.txt').write_text(marker)
    (dest/'VERIFIED.txt').write_text(marker)
    if recheck:
        write_json(attempt/'status.json',dict(state='image-verified-runtime-pending',recheck=recheck,report=str(report),time=time.time()))
    print('STATIC IMAGE CHECKS PASSED; not boot-tested:',archive,digest)
    vlock.close()
    if source_lock:source_lock.close()

RUNTIME_PENDING='''# Experimental candidate: runtime admission pending

Static image checks do not admit a phone trial. Before any flash, complete the unrooted early-boot
baseline contract, concrete slot-a fallback/recovery decision and the owner's separate go/no-go.
The current candidate has not booted. Keep the known-good recovery ZIP and follow the staged
K -> K+D -> K+D+S protocol. No display timing benefit or protected-mode runtime compatibility is claimed.
'''

# --- simple mode -----------------------------------------------------------------------------------------

def locate_archive(attempt_id,exit_record,identity,recheck):
    """The producing ZIP: out/ while it still is this attempt's, else (rechecks only) a preserved copy of the same
    size. Its digest is checked against build-exit while it is copied; a name alone never selects it."""
    size,mtime=exit_record.get('zip_bytes'),exit_record.get('zip_mtime_ns')
    if ZIP.is_file() and ZIP.stat().st_size==size and ZIP.stat().st_mtime_ns==mtime and mtime>=identity['started_ns']:
        return ZIP
    if not recheck:
        raise Defect('Producing ZIP is missing or changed since build-exit; initial verification reads it from out/','attempt.provenance')
    where=paths.for_build(BUILD)
    name=f'lineage_klimt-{BUILD}-img.zip'
    candidates=[where['staging']/attempt_id/name,*sorted((where['staging']/attempt_id/'rechecks').glob('*/'+name))]
    receipt_path=where['debug']/'PROMOTED.json'
    if receipt_path.is_file():
        receipt=json.loads(receipt_path.read_text())
        if receipt.get('attempt')==attempt_id and receipt.get('archive_sha256')==exit_record.get('zip_sha256'):
            candidates.append(Path(receipt['delivery'])/name)  # read-only: verification never writes there
    for candidate in candidates:
        if candidate.is_file() and candidate.stat().st_size==size:
            return candidate
    raise Missing('No preserved copy of the producing ZIP (out/ has moved on); looked in: '+', '.join(map(str,candidates)),'attempt.provenance')

def staging_evidence(attempt,exit_record):
    """The packaging-time staging evidence named in build-exit.json, with every file hash checked."""
    recorded=exit_record.get('staging_evidence')
    root=attempt/'staging-evidence'
    if not recorded:
        raise Missing('build-exit.json has no staging evidence ('+str(exit_record.get('staging_evidence_error','not captured'))[-300:]+'); '
                      'this attempt cannot be verified in simple mode','attempt.provenance')
    present={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()} if root.is_dir() else set()
    if present!=set(recorded):
        raise Defect('Staging evidence files differ from build-exit: '+str(sorted(present^set(recorded))[:10]),'attempt.provenance')
    for rel,digest in recorded.items():
        if sha(root/rel)!=digest:raise Defect('Staging evidence changed after packaging: '+rel,'attempt.provenance')
    return root

def simple_main(attempt,identity,review,recheck,tool_review,exit_record,ready,tools_match):
    import simple_checks as sc
    record=verification.validate_record(ready['verification'])
    required=verification.required_checks(record)
    tracks=[t for t in verification.TRACKS if t in record['extras']]
    attempt_id=identity['attempt']; report=C/attempt_id
    results=[]
    def step(check_id,fn,summary):
        began=time.monotonic()
        try:
            detail=fn()
        except Exception as e:
            if isinstance(e,(Defect,Missing)) and not e.check:e.check=check_id
            outcome='fail' if isinstance(e,Defect) else 'error'
            results.append(dict(id=check_id,outcome=outcome,summary=str(e)[:2000],evidence=[],elapsed_seconds=round(time.monotonic()-began,1)))
            if report.is_dir():write_json(report/'checks-progress.json',results)
            raise
        results.append(dict(id=check_id,outcome='pass',summary=summary(detail) if callable(summary) else summary,
                            evidence=sorted((detail or {}).get('_evidence',[])),detail={k:v for k,v in (detail or {}).items() if k!='_evidence'},
                            elapsed_seconds=round(time.monotonic()-began,1)))
        if report.is_dir():write_json(report/'checks-progress.json',results)
        print('PASS',check_id,f"{results[-1]['elapsed_seconds']}s",flush=True)
        return detail
    avbtool=S/'external/avb/avbtool.py'
    lpdump,unpack,simg2img=paths.TOOLS/'lpdump',paths.TOOLS/'unpack_bootimg',paths.TOOLS/'simg2img'
    needed=[avbtool,lpdump,unpack,'lz4','gzip']
    if 'kernel' in record['extras'] or tracks:needed+=[simg2img,'nm','fsck.erofs','debugfs']
    sc.require_tools(needed)
    state={}
    def provenance():
        heads=ready_heads(ready)
        if foreign_processes():raise Missing('Competing build/extraction exists')
        try:live_heads(heads)
        except RuntimeError as e:raise Defect(str(e)) from e
        state['heads']=heads
        state['source']=locate_archive(attempt_id,exit_record,identity,recheck)
        state['evidence']=staging_evidence(attempt,exit_record)
        return dict(source_heads=len(heads),archive_source=str(state['source']),build_exit_sha256=exit_record['zip_sha256'],
                    staging_evidence=len(exit_record['staging_evidence']))
    began=time.monotonic()
    try:
        detail=provenance()
    except (Defect,Missing) as e:
        e.check=e.check or 'attempt.provenance'
        raise
    evidence=attempt
    if recheck:
        report=report/'rechecks'/recheck
        report.mkdir(parents=True,exist_ok=False)
        evidence=attempt/'rechecks'/recheck
        evidence.mkdir(parents=True,exist_ok=False)
        shutil.copyfile(tool_review,evidence/'TOOL_REVIEW.json')
    if recheck or ready.get('candidate_evidence'):
        write_json(evidence/'effective-ready.json',ready,True)
    heads=state['heads']
    if capture_manifest(evidence/'preverify.xml')!=heads:raise Defect('Preverify manifest drift','attempt.provenance')
    if (report/'VERIFIED.txt').exists():raise RuntimeError('Already verified; no overwrite')
    results.append(dict(id='attempt.provenance',outcome='pass',
                        summary='Build exit 0 (installclean and empty staging held), live heads equal readiness, ZIP and staging evidence bound to build-exit',
                        evidence=['build-exit.json','preverify.xml'],detail=detail,elapsed_seconds=round(time.monotonic()-began,1)))
    source=state['source']
    with zipfile.ZipFile(source) as z:unpacked=sum(i.file_size for i in z.infolist())
    fs_gib=22 if tracks else (2 if 'kernel' in record['extras'] else 0)
    free=space()
    need=dict(host=exit_record['zip_bytes']/GIB+10,output=unpacked/GIB+2+fs_gib+(6 if record['candidate'] else 0),source=2)
    if any(free[k]<need[k] for k in need):
        raise Missing('Headroom below this mode\'s need: free '+json.dumps({k:round(v,1) for k,v in free.items()})+' need '+json.dumps({k:round(v,1) for k,v in need.items()}))
    extract=X/attempt_id
    dest=paths.for_build(BUILD)['staging']/attempt_id
    if recheck:
        extract=extract/'rechecks'/recheck
        dest=dest/'rechecks'/recheck
    dest.mkdir(parents=True,exist_ok=False)
    tmp=extract/'tmp'
    tmp.mkdir(parents=True,exist_ok=False)
    img=extract/'img'
    archive=dest/f'lineage_klimt-{BUILD}-img.zip'
    partial=archive.with_suffix(archive.suffix+'.partial')
    def archive_integrity():
        digest=sc.copy_with_digest(source,partial,exit_record['zip_sha256'])
        if archive.exists():raise RuntimeError('Attempt archive exists')
        partial.rename(archive)
        members=sc.extract_members(source,img)
        write_json(report/'archive-inventory.json',members,True)
        write_json(report/'image-files.json',[dict(path=m['name'],bytes=m['bytes'],sha256=m['sha256']) for m in sorted(members,key=lambda m:m['name'])],True)
        state['digest']=digest
        return dict(sha256=digest,entries=len(members),uncompressed_bytes=unpacked,_evidence=['archive-inventory.json','image-files.json'])
    step('archive.integrity',archive_integrity,lambda d:f"19 expected entries, CRC-checked; copy sha256 equals build-exit ({d['sha256'][:12]})")
    digest=state['digest']
    step('avb.chain',lambda:sc.avb_chain(img,avbtool,record['baseline']['avb_keys']),
         'avbtool verify_image --follow_chain_partitions passed; vbmeta/chain keys equal baseline '+record['baseline']['build'])
    step('flash.layout',lambda:sc.flash_layout(img,{'author':paths.COMPARE/'author/img','build9':paths.COMPARE/'b9/img'},lpdump),
         'super_empty, fastboot-info.txt and android-info.txt match the author and build9 references')
    step('dtb.live',lambda:sc.dtb_live(img,paths.PARTITIONS/'dtbo_b.img',paths.COMPARE/'b9/img/dtbo.img',
                                         paths.COMPARE/'live/unpack/XiaomiBuilds_vendor_boot_b/dtb',avbtool,unpack,tmp),
         'DTBO payload and vendor_boot DTB equal the saved live slot b')
    def identity_metadata():
        banner=sc.boot_banner(img/'boot.img',unpack,tmp)
        return sc.identity_metadata(state['evidence']/'props',banner,BUILD,ready.get('kernel_expectation'))
    step('identity.metadata',identity_metadata,lambda d:f"{d['assertions']} identity assertions on staged build.prop files; packaged kernel banner matches")
    step('staging.clean',lambda:sc.staging_clean(state['evidence']),
         lambda d:f"{d['staged_files']} staged files all product installs (kernel modules excepted); only {d['telecom']}")
    def signing():
        pem=S/'vendor/evolution-priv/keys/platform.x509.pem'
        if sha(pem)!=ready['public_certificate_sha256']['platform']:
            raise Defect('platform.x509.pem differs from the reviewed certificate digest')
        facts=json.loads((state['evidence']/'facts.json').read_text())
        return sc.platform_signer((state['evidence']/'framework-res.apksigner.txt').read_text(),facts.get('apksigner_exit'),pem.read_text())
    step('signing.platform',signing,'staged framework-res.apk verifies with the single reviewed platform signer')
    env=dict(os.environ,KLIMT_BUILD=BUILD,EVOX_EXTRACT=str(extract),EVOX_TMP=str(tmp),EVOX_REPORT=str(report),
             EVOX_READY=str(evidence/'effective-ready.json' if recheck or ready.get('candidate_evidence') else attempt/'BUILD_READY.json'))
    audit=None
    if record['candidate']:
        import candidate_gates
        candidate_gates.validate_ready(ready, ready['reviewed_project_heads'])
        audit=candidate_gates.revalidate(ready['candidate_evidence']['kernel_audit'])
    if 'kernel' in record['extras'] or tracks:
        parts=list(sc.PARTITIONS) if tracks else ['vendor_dlkm','system_dlkm']
        sc.extract_filesystems(img,extract/'fs',parts,simg2img,tmp,'kernel.modules' if not tracks else 'track.'+tracks[0])
        sc.unpack_vendor_ramdisks(img/'vendor_boot.img',unpack,tmp,'kernel.modules')
    if 'kernel' in record['extras']:
        import kernel_artifact
        symvers=kernel_artifact.audited_symvers(audit) if audit else S/'out/target/product/klimt/obj/KERNEL_OBJ/Module.symvers'
        step('kernel.modules',lambda:sc.kernel_modules(symvers,[extract/'fs/vendor_dlkm/lib/modules',tmp/'evx_rd',extract/'fs/system_dlkm']),
             lambda d:f"{d['modules']} modules, 0 CRC mismatches, unresolved {d['unresolved']}")
    for track in tracks:
        step('track.'+track,lambda t=track:dict(results=run_tracks(ready.get('image_checks',[]),env,report,{t})),
             'registered '+track+' image check passed')
    if record['candidate']:
        import kernel_artifact, rollback_security, candidate_gates
        def binding():
            found=kernel_artifact.validate(audit,ready['reviewed_project_heads'],img/'boot.img',extract/'fs/system_dlkm',digest,S)
            write_json(report/'kernel-artifact-binding.json',found,True)
            write_json(report/'filesystem-files.json',inventory(extract/'fs'),True)
            kernel_artifact.validate_receipt(found,audit,ready['reviewed_project_heads'],digest,
                                             json.loads((report/'image-files.json').read_text()),
                                             json.loads((report/'filesystem-files.json').read_text()))
            return dict(_evidence=['kernel-artifact-binding.json','image-files.json','filesystem-files.json'],
                        filesystems=sorted(p.name for p in (extract/'fs').iterdir()))
        step('candidate.kernel_binding',binding,'packaged Image, config and GKI modules bind to the audited kernel')
        def rollback():
            # Packaged AVB/boot headers; reported SPL props from the staged build.prop files (same layout).
            view=extract/'rollback-view'
            view.mkdir()
            (view/'img').symlink_to(img)
            (view/'fs').symlink_to(state['evidence']/'props')
            baseline=candidate_gates.revalidate(ready['candidate_evidence']['rollback_baseline'])['security']
            security=rollback_security.collect(view,avbtool,ready['security']['platform_security_patch'])
            write_json(report/'rollback-security-candidate.json',security,True)
            write_json(report/'rollback-security-equality.json',rollback_security.compare(baseline,security),True)
            return dict(_evidence=['rollback-security-candidate.json','rollback-security-equality.json'])
        step('candidate.rollback_security',rollback,'rollback indexes, AVB and security metadata equal the controlled baseline')
    if capture_manifest(evidence/'postverify.xml')!=heads:raise Defect('Postverify manifest drift','attempt.provenance')
    try:live_heads(heads)
    except RuntimeError as e:raise Defect(str(e),'attempt.provenance') from e
    tools_match()
    order={k:i for i,k in enumerate(required)}
    if sorted(r['id'] for r in results)!=sorted(required):
        raise RuntimeError('Executed checks differ from the sealed list: '+str([r['id'] for r in results]))
    results.sort(key=lambda r:order[r['id']])
    not_selected=[('track.'+t) for t in verification.TRACKS if t not in tracks]+([] if 'kernel' in record['extras'] else ['kernel.modules'])
    not_selected+=['historical rows (195)','full filesystem extraction and inventories','packaged-vs-staged file equality']
    tools={str(p):sha(p) for p in (avbtool,lpdump,unpack) if Path(p).is_file()}
    out=dict(schema=2,attempt=attempt_id,run=recheck or 'initial',recheck=recheck,verification=record,
             archive=str(archive),archive_sha256=digest,archive_bytes=archive.stat().st_size,source_heads=heads,
             checks=results,not_selected=not_selected,runtime_unvalidated=True,time=time.time(),
             environment=dict(python=sys.version.split()[0],platform=sys.platform,tools_sha256=tools))
    if ready.get('candidate_evidence'):
        out['candidate_evidence']=ready['candidate_evidence']
        out['kernel_expectation']=ready['kernel_expectation']
        out['kernel_artifact_evidence']={name:sha(report/name) for name in ('kernel-artifact-binding.json','image-files.json','filesystem-files.json')}
        out['rollback_security']={name:sha(report/name) for name in ('rollback-security-candidate.json','rollback-security-equality.json')}
    write_json(report/'RESULTS.json',out,True)
    extras=', '.join(record['extras']) or 'none'
    (report/'COMPARISON.md').write_text(f'''# {BUILD} simple verification — {attempt_id}

Mode **simple** (extras: {extras}). Baseline for keys and escalation: {record['baseline']['build']}.
Selection: {'; '.join(record['reasons']) or 'routine'}.

Passed: {', '.join(r['id'] for r in results)}. The archive is the producing build's ZIP (sha256 `{digest}`), with the
expected 19 entries and valid CRCs; the AVB chain verifies with the baseline's keys; super_empty,
fastboot-info and android-info match the references; DTBO and the vendor_boot DTB equal the live slot b. Identity
props and the Telecom/staging checks read the staging captured at packaging time, not the packed images.

Not run: {', '.join(not_selected)}. A packaged file that differs from staging, a duplicate package identity under
another path, Ninja producer drift and behavioral or ABI regressions are not detected by this mode.

**Not boot-tested.** Say "image-checked" until the phone has booted this build.
''')
    scripts=future_flash_scripts(dest,archive,digest)
    shutil.copyfile(report/'RESULTS.json',dest/'RESULTS.json')
    shutil.copyfile(report/'COMPARISON.md',dest/'COMPARISON.md')
    for name in dict(out.get('rollback_security',{}),**out.get('kernel_artifact_evidence',{})):
        shutil.copyfile(report/name,dest/name)
    for name in ('prebuild.xml','postbuild.xml','postverify.xml'):
        shutil.copyfile(evidence/name if name=='postverify.xml' else attempt/name,dest/name)
    if review:shutil.copyfile(tool_review,dest/'TOOL_REVIEW.json')
    (dest/'README.md').write_text(f'''# {BUILD} image — {attempt_id}

Build target: lineage_klimt-cp2a-user. **Simple** static checks passed (see COMPARISON.md for what that covers and
what it does not). **Not boot-tested**. Keep the previous boot-tested ZIP available.

The supplied Windows `.bat` and Linux `.sh` wrappers check the ZIP hash and the klimt product, select slot b with
`fastboot --slot=b update --skip-reboot`, omit data wiping and run `fastboot reboot` only after a successful
update. Failed flashes remain in fastboot. Run only after authorizing the flash, including its successful
reboot unless the owner explicitly asks to stay in fastboot. In Windows run `{scripts[1].name} /flash`; in Linux run
`bash ./{scripts[0].name} --flash`. `sha256sum -c SHA256SUMS` validates the complete delivery set.
''')
    if ready.get('candidate_evidence'):
        (dest/'RUNTIME_PENDING.md').write_text(RUNTIME_PENDING)
    if sc.file_sha(archive)!=digest:  # read back the delivered bytes; size or mtime is not an identity check
        raise Defect('Delivered archive differs from the producing digest','archive.integrity')
    marker=(BUILD+' SIMPLE static checks passed (archive, AVB, flash layout, live DTB, staged identity props, staging, platform signer'
            +(', extras: '+extras if record['extras'] else '')+'). Filesystem contents were not inspected. NOT boot-tested.\n')
    files=sorted(p for p in dest.iterdir() if p.is_file())
    sums={p.name:(digest if p==archive else sha(p)) for p in files}
    sums['VERIFIED.txt']=hashlib.sha256(marker.encode()).hexdigest()
    (dest/'SHA256SUMS').write_text(''.join(sums[name]+'  '+name+'\n' for name in sorted(sums)))
    (report/'VERIFIED.txt').write_text(marker)
    (dest/'VERIFIED.txt').write_text(marker)
    if recheck:
        write_json(attempt/'status.json',dict(state='image-verified-runtime-pending',recheck=recheck,report=str(report),mode='simple',time=time.time()))
    print('SIMPLE STATIC CHECKS PASSED; not boot-tested:',archive,digest)

def record_failure(attempt,recheck,error):
    """verify-exit.<run>.json beside the attempt: exit code, kind, failing check. The controller reads it."""
    code=verification.exit_code(error)
    kind={1:'artifact-defect',2:'missing-tool-or-evidence',3:'unexpected-error',130:'interrupted'}.get(code,'unexpected-error')
    try:
        write_json(attempt/f"verify-exit.{recheck or 'initial'}.json",dict(exit=code,kind=kind,check=getattr(error,'check',None),
                   error=f'{type(error).__name__}: {error}'[:4000],time=time.time()))
    except OSError:
        pass
    return code

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('attempt')
    parser.add_argument('--recheck')
    parser.add_argument('--tool-review')
    args=parser.parse_args()
    if args.tool_review and not args.recheck:parser.error('--tool-review requires --recheck')
    target=wsl_path(args.attempt)
    try:
        main(target,args.recheck,wsl_path(args.tool_review) if args.tool_review else None)
    except (Exception,KeyboardInterrupt) as e:
        code=record_failure(target,args.recheck,e)
        import traceback
        traceback.print_exc()
        print(f'VERIFICATION STOPPED (exit {code}, check {getattr(e,"check",None)}): {e}',file=sys.stderr)
        sys.exit(code)
