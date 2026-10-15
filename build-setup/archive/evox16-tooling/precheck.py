#!/usr/bin/env python3
"""P5 module compile supervisor; it has no image-verifier or full-build path.

Approval applies only to a frozen explicit module list. Compile evidence never
changes pending P5 gates or creates P8 approval. The full build controller,
wrapper and verifier remain unchanged.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from controller import (B,S,L,D,O,sha,wsl_path,write_json,proc,owned,stop_owned,
                        lock,manifest_heads,live_heads,capture_manifest,
                        check_capacity,foreign_processes,tooling_hashes,require_tooling_frozen)

SCOPE='evox16-p5-module-precheck'
FORBIDDEN={'updatepackage','otapackage','evolution','dist','droid','all','checkbuild',
           'clean','clobber','installclean','dataclean','images','systemimage',
           'vendorimage','bootimage','target-files-package'}
REQUIRED_EXCLUDED={'kernel/xiaomi/klimt','kernel/xiaomi/klimt-prebuilt','vendor/xiaomi/klimt','hardware/xiaomi','device/mediatek/sepolicy_vndr'}
REQUIRED_CERTS={'platform','releasekey','shared','media','networkstack'}

def validate_static_contract(ready):
    if not isinstance(ready,dict) or ready.get('approved') is not True or ready.get('approval_scope')!=SCOPE:
        raise RuntimeError('A distinct root-approved P5 module-precheck contract is required')
    if ready.get('target')!='lineage_klimt-cp2a-user' or ready.get('runtime_unvalidated') is not True:
        raise RuntimeError('Precheck target/runtime scope mismatch')
    if any(k in ready for k in ('image_checks','full_build_approved','checks')):
        raise RuntimeError('P8/image verification fields are not valid precheck approval')
    checks=ready.get('static_checks',[])
    if not checks or any(not isinstance(c,dict) or c.get('pass') is not True or not c.get('name') or not c.get('evidence') for c in checks):
        raise RuntimeError('Root-reviewed static checks must explicitly pass with evidence')
    if len({c['name'] for c in checks})!=len(checks):
        raise RuntimeError('Static check names duplicate')
    modules=ready.get('modules',[])
    if not isinstance(modules,list) or not 1<=len(modules)<=64 or any(not isinstance(name,str) for name in modules) or len(set(modules))!=len(modules):
        raise RuntimeError('One to 64 distinct reviewed module names required')
    for name in modules:
        if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.+@-]*',name) or name in FORBIDDEN:
            raise RuntimeError('Invalid/out-of-scope precheck target: '+str(name))
    pending=ready.get('pending_module_gates',[])
    if not isinstance(pending,list) or not pending or any(not isinstance(g,dict) or g.get('status')!='pending' or not g.get('name') for g in pending):
        raise RuntimeError('Pending module gates must remain explicitly pending')
    if len({g['name'] for g in pending})!=len(pending):
        raise RuntimeError('Pending module gate names duplicate')
    return modules

def precheck_readiness(path):
    ready=json.loads(path.read_text())
    validate_static_contract(ready)
    snapshot=wsl_path(ready['snapshot'])
    if sha(snapshot)!=ready['sha256']:raise RuntimeError('Static snapshot hash mismatch')
    heads=manifest_heads(snapshot.read_bytes())
    if ready.get('reviewed_project_heads')!=heads:raise RuntimeError('Full frozen project-head mapping required')
    excluded=ready.get('excluded_heads',{})
    if not REQUIRED_EXCLUDED<=set(excluded) or any(heads.get(p)!=v for p,v in excluded.items()):
        raise RuntimeError('Excluded input protection missing/mismatched')
    live_heads(heads)
    if not (S/'out').is_symlink() or (S/'out').resolve()!=O:
        raise RuntimeError('Expected incremental out symlink absent')
    for path in ('/mnt/wsl/evox','/mnt/wsl/build'):
        if subprocess.run(['mountpoint','-q',path]).returncode:
            raise RuntimeError('Required ext4 disk not mounted: '+path)
    certs=ready.get('public_certificate_sha256',{})
    if set(certs)!=REQUIRED_CERTS:raise RuntimeError('All five existing certificate file digests required')
    for name,digest in certs.items():
        if sha(S/'vendor/evolution-priv/keys'/f'{name}.x509.pem')!=digest:
            raise RuntimeError('Existing certificate digest mismatch: '+name)
    current,emergency=check_capacity(ready)
    return ready,heads,current,emergency

def compile_argv(ready):
    return ['bash',str(B/'precheck-build.sh'),*validate_static_contract(ready)]

def watchdog_argv(attempt):
    # Reuse only the reviewed independent ownership/disk watchdog, never run/resume.
    return [sys.executable,'-B',str(B/'controller.py'),'watchdog',str(attempt)]

def progress(attempt,owner):
    from controller import space
    states=[]
    for path in Path('/proc').iterdir():
        if path.name.isdigit():
            state=proc(int(path.name))
            if state and state['sid']==owner['sid']:states.append(state)
    with open(attempt/'progress.jsonl','a') as f:
        f.write(json.dumps(dict(operation='focused-precheck',time=time.time(),processes=states,
                               log_bytes=(attempt/'precheck.log').stat().st_size,free_gib=space()))+'\n')

def preserve(attempt,debug):
    for name in ('status.json','PRECHECK_READY.json','owner.json','precheck-exit.json','watchdog-terminal.json',
                 'disk-stop.json','tool-error.json','RESULTS.json','precheck-before.xml','precheck-after.xml','tooling-snapshot.json'):
        if (attempt/name).exists():shutil.copyfile(attempt/name,debug/name)
    for error in attempt.glob('precheck-resume-error.*.json'):
        shutil.copyfile(error,debug/error.name)

def finalize(attempt,ready,heads,rc):
    """Record honest compile/source evidence on both success and failure."""
    if json.loads((attempt/'PRECHECK_READY.json').read_text())!=ready:
        raise RuntimeError('Static precheck approval changed during compilation')
    after=capture_manifest(attempt/'precheck-after.xml')
    if after!=heads:raise RuntimeError('Source manifest changed during focused precheck')
    live_heads(heads)
    require_tooling_frozen(attempt)
    result=dict(operation='focused-precheck',target=ready['target'],modules=ready['modules'],
        command=['m','-j12',*ready['modules']],exit=rc,compile_group_exit_zero=(rc==0),
        source_heads=heads,pre_manifest_sha256=sha(attempt/'precheck-before.xml'),
        post_manifest_sha256=sha(attempt/'precheck-after.xml'),source_identity_unchanged=True,
        pending_module_gates=ready['pending_module_gates'],image_verification_performed=False,
        full_build_approval_issued=False,runtime_unvalidated=True,time=time.time())
    write_json(attempt/'RESULTS.json',result,True)
    write_json(attempt/'status.json',dict(operation='focused-precheck',state='compile-exited-zero' if rc==0 else 'compile-failed',
        exit=rc,source_identity_unchanged=True,image_verification_performed=False,full_build_approval_issued=False,time=time.time()))
    return 0 if rc==0 else 1

def record_exit(attempt,ready,rc):
    path=attempt/'precheck-exit.json'
    if not path.exists():
        write_json(path,dict(operation='focused-precheck',exit=rc,time=time.time(),modules=ready['modules'],producer='supervisor-observed'),True)
    else:
        record=json.loads(path.read_text())
        if record.get('operation')!='focused-precheck' or record.get('exit')!=rc or record.get('modules')!=ready['modules']:
            raise RuntimeError('Precheck producer/supervisor exit evidence disagrees')

def run(attempt_id,ready_path):
    if not re.fullmatch(r'evox16-precheck\d{2,}',attempt_id):raise RuntimeError('Precheck ID must be evox16-precheckNN')
    source_lock=lock(L/'source.lock')
    attempt=L/attempt_id;debug=D/attempt_id
    owner=None;child=None;watch=None
    created=False;debug_created=False
    try:
        if foreign_processes():raise RuntimeError('Competing build/extraction exists')
        attempt.mkdir();created=True
        debug.mkdir(parents=True,exist_ok=False);debug_created=True
        write_json(attempt/'status.json',dict(operation='focused-precheck',state='static-preflight',time=time.time()))
        ready,heads,current,emergency=precheck_readiness(ready_path)
        shutil.copyfile(ready_path,attempt/'PRECHECK_READY.json')
        if json.loads((attempt/'PRECHECK_READY.json').read_text())!=ready:
            raise RuntimeError('Precheck approval changed during preflight')
        write_json(attempt/'tooling-snapshot.json',tooling_hashes(),True)
        if capture_manifest(attempt/'precheck-before.xml')!=heads:raise RuntimeError('Live manifest does not match static frozen inputs')
        argv=compile_argv(ready)
        with open(attempt/'precheck.log','xb') as log:
            child=subprocess.Popen(argv,cwd=S,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,
                pass_fds=(source_lock.fileno(),),env=dict(os.environ,EVOX16_PRECHECK=str(attempt)))
        owner=proc(child.pid)
        if not owner:
            rc=child.wait();record_exit(attempt,ready,rc)
            write_json(attempt/'watchdog-terminal.json',dict(operation='focused-precheck',reason='wrapper-finished-before-identity-capture',time=time.time()),True)
            return finalize(attempt,ready,heads,rc)
        state=dict(attempt=attempt_id,operation='focused-precheck',build=owner,controller=proc(os.getpid()),
            started_ns=time.time_ns(),initial_free_gib=current,emergency=emergency,modules=ready['modules'],command=argv,
            ready_sha256=sha(attempt/'PRECHECK_READY.json'))
        write_json(attempt/'owner.json',state,True)
        with open(attempt/'watchdog.log','xb') as log:
            watch=subprocess.Popen(watchdog_argv(attempt),stdout=log,stderr=subprocess.STDOUT,
                                   start_new_session=True,pass_fds=(source_lock.fileno(),))
        write_json(attempt/'status.json',dict(operation='focused-precheck',state='compiling-modules',owner=owner,
            modules=ready['modules'],pending_module_gates=ready['pending_module_gates'],time=time.time()))
        while child.poll() is None:
            progress(attempt,owner)
            if watch.poll() is not None and owned(owner):
                stop_owned(owner);raise RuntimeError('Precheck watchdog ended unexpectedly; owned compile stopped')
            time.sleep(15)
        rc=child.wait()
        record_exit(attempt,ready,rc)
        watch.wait(timeout=35)
        return finalize(attempt,ready,heads,rc)
    except Exception as e:
        if owner and owned(owner):stop_owned(owner)
        if created and child and not (attempt/'precheck-exit.json').exists() and child.poll() is not None:
            write_json(attempt/'precheck-exit.json',dict(operation='focused-precheck',exit=child.returncode,
                producer='supervisor-observed',time=time.time()),True)
        if created:
            write_json(attempt/'tool-error.json',dict(operation='focused-precheck',error=str(e),time=time.time()),True)
            write_json(attempt/'status.json',dict(operation='focused-precheck',state='tool-failed',error=str(e),time=time.time()))
        raise
    finally:
        if created and debug_created:preserve(attempt,debug)
        source_lock.close()

def resume(attempt):
    monitor_lock=lock(attempt/'precheck-monitor.lock')
    source_lock=None
    state=None
    try:
        state=json.loads((attempt/'owner.json').read_text())
        if state.get('operation')!='focused-precheck':raise RuntimeError('Only a focused precheck can be resumed here')
        if owned(state['controller']):raise RuntimeError('Recorded original precheck controller is still active')
        while owned(state['build']):progress(attempt,state['build']);time.sleep(15)
        path=attempt/'precheck-exit.json'
        if not path.exists():
            write_json(attempt/'status.json',dict(operation='focused-precheck',state='wrapper-lost-no-exit-evidence',time=time.time()))
            raise RuntimeError('Compile wrapper disappeared without exit evidence')
        for _ in range(30):
            try:source_lock=lock(L/'source.lock');break
            except BlockingIOError:time.sleep(1)
        if source_lock is None:raise RuntimeError('Source lock remains owned; no duplicate compile is launched')
        if (attempt/'RESULTS.json').exists():
            print('Precheck already finalized; no compile or verification started')
            return 0 if json.loads((attempt/'RESULTS.json').read_text())['exit']==0 else 1
        if sha(attempt/'PRECHECK_READY.json')!=state.get('ready_sha256'):
            raise RuntimeError('Precheck approval no longer matches original ownership evidence')
        ready=json.loads((attempt/'PRECHECK_READY.json').read_text());validate_static_contract(ready)
        record=json.loads(path.read_text())
        if record.get('operation')!='focused-precheck' or record.get('modules')!=ready['modules']:
            raise RuntimeError('Precheck producer identity/targets mismatch')
        return finalize(attempt,ready,ready['reviewed_project_heads'],record['exit'])
    except Exception as e:
        write_json(attempt/f'precheck-resume-error.{time.time_ns()}.json',dict(operation='focused-precheck',error=str(e),time=time.time()),True)
        if state and state.get('operation')=='focused-precheck' and state.get('controller') and not owned(state['controller']):
            existing=json.loads((attempt/'status.json').read_text())
            if existing.get('state')!='wrapper-lost-no-exit-evidence':
                write_json(attempt/'status.json',dict(operation='focused-precheck',state='tool-failed-resume',error=str(e),time=time.time()))
        raise
    finally:
        debug=D/attempt.name
        if debug.exists():preserve(attempt,debug)
        if source_lock:source_lock.close()
        monitor_lock.close()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['run','resume','stop','status'])
    parser.add_argument('attempt');parser.add_argument('ready',nargs='?')
    args=parser.parse_args()
    if args.mode=='run':
        if not args.ready:parser.error('run requires distinct PRECHECK_READY.json')
        return run(args.attempt,wsl_path(args.ready))
    attempt=wsl_path(args.attempt)
    if not attempt.is_absolute():attempt=L/args.attempt
    if args.mode=='status':
        status=json.loads((attempt/'status.json').read_text())
        if status.get('operation')!='focused-precheck':raise RuntimeError('Focused precheck status required')
        print(json.dumps(status,indent=2));return 0
    state=json.loads((attempt/'owner.json').read_text())
    if state.get('operation')!='focused-precheck':raise RuntimeError('Precheck ownership record required')
    if args.mode=='resume':return resume(attempt)
    if args.mode=='stop':print('owned precheck signalled' if stop_owned(state['build']) else 'no matching precheck process; no signal')
    return 0

if __name__=='__main__':sys.exit(main())
