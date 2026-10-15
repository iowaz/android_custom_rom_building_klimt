#!/usr/bin/env python3
"""Attempt-owned launcher, resource supervisor, independent disk watchdog and stop.

No source repair/retry/phone action is performed here. A new attempt always needs
a new directory and the reviewed BUILD_READY.json input. Linux /proc start ticks,
boot ID, session and process group identify the build before any signal.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

B = Path(__file__).resolve().parent
S = Path('/mnt/wsl/evox/src')
L = Path('/mnt/wsl/evox/logs/evox16')
D = Path('/mnt/c/XiaomiBuilds/debug/evox16')
C = Path('/mnt/c/XiaomiBuilds/compare/evox16')
O = Path('/mnt/wsl/build/evox-out')
ZIP = O/'target/product/klimt/lineage_klimt-img.zip'
GIB = 1024**3

def wsl_path(value):
    if re.match(r'^[A-Za-z]:[/\\]', str(value)):
        return Path('/mnt/'+value[0].lower()+'/'+value[3:].replace('\\', '/'))
    return Path(value)

def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for part in iter(lambda: f.read(4*1024*1024), b''):
            h.update(part)
    return h.hexdigest()

def write_json(path, data, exclusive=False):
    if exclusive:
        with open(path, 'x') as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write('\n')
        return
    tmp = path.with_name(path.name+'.tmp.'+str(os.getpid()))
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True)+'\n')
    os.replace(tmp, path)

def proc(pid):
    try:
        text = Path(f'/proc/{pid}/stat').read_text()
        fields = text[text.rfind(')')+2:].split()
        if fields[0] == 'Z':
            return None
        return dict(pid=int(pid), pgrp=int(fields[2]), sid=int(fields[3]),
                    start=int(fields[19]), cpu=int(fields[11])+int(fields[12]),
                    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    except (FileNotFoundError, ProcessLookupError):
        return None

def owned(owner):
    current = proc(owner['pid'])
    return bool(current and all(current[k] == owner[k] for k in ('pid','pgrp','sid','start','boot')))

def same_process(identity):
    current=proc(identity['pid'])
    return bool(current and all(current[k]==identity[k] for k in ('pid','start','boot')))

def stop_owned(owner, grace=10):
    if not owned(owner) or owner['pid'] != owner['pgrp'] or owner['pid'] != owner['sid']:
        return False
    if owner['sid'] == os.getsid(0):
        raise RuntimeError('Refusing to signal caller session')
    # Capture each concrete process before TERM. The wrapper may exit before a
    # child that ignores TERM; escalation then targets those exact old members,
    # never a numeric group/session ID that could have been reused.
    members=[]
    for path in Path('/proc').iterdir():
        if path.name.isdigit():
            entry=proc(int(path.name))
            if entry and entry['sid']==owner['sid']:
                fd=None
                try:
                    if hasattr(os,'pidfd_open'):fd=os.pidfd_open(entry['pid'])
                    if same_process(entry):members.append((entry,fd))
                    elif fd is not None:os.close(fd)
                except ProcessLookupError:
                    if fd is not None:os.close(fd)
    def send(entry,fd,signum):
        if not same_process(entry):return
        try:
            if fd is not None and hasattr(signal,'pidfd_send_signal'):
                signal.pidfd_send_signal(fd,signum)
            elif same_process(entry):
                os.kill(entry['pid'],signum)
        except ProcessLookupError:
            pass
    try:
        if not owned(owner):
            return False
        for entry,fd in members:send(entry,fd,signal.SIGTERM)
        deadline = time.monotonic()+grace
        while any(same_process(entry) for entry,fd in members) and time.monotonic() < deadline:
            time.sleep(.1)
        for entry,fd in members:send(entry,fd,signal.SIGKILL)
        return True
    finally:
        for entry,fd in members:
            if fd is not None:os.close(fd)

def lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    f = open(path, 'a+')
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception:
        f.close()
        raise
    return f

def tooling_hashes():
    return {str(p.relative_to(B)):sha(p) for p in sorted(B.rglob('*'))
            if p.is_file() and p.suffix in {'.py','.sh','.json','.sha256'}}

def require_tooling_frozen(attempt):
    expected=json.loads((attempt/'tooling-snapshot.json').read_text())
    if tooling_hashes()!=expected:
        raise RuntimeError('Reviewed tooling changed during this attempt')

def manifest_heads(data):
    root = ET.fromstring(data)
    result = {}
    for p in root.findall('project'):
        name = p.get('path') or p.get('name')
        rev = p.get('revision', '')
        if name in result or not re.fullmatch(r'[0-9a-f]{40}', rev):
            raise RuntimeError('Manifest duplicate path or nonimmutable revision: '+str(name))
        result[name] = rev
    return result

def capture_manifest(dest):
    subprocess.run(['repo','manifest','-r','-o',str(dest)], cwd=S, check=True)
    return manifest_heads(dest.read_bytes())

def live_heads(expected):
    for path, head in expected.items():
        actual = subprocess.check_output(['git','-C',str(S/path),'rev-parse','HEAD'], text=True).strip()
        if actual != head:
            raise RuntimeError('Source HEAD drift: '+path)
        status = subprocess.check_output(['git','-C',str(S/path),'status','--porcelain','--untracked-files=normal'], text=True)
        if status:
            raise RuntimeError('Dirty/untracked reviewed project: '+path)

def space():
    return {name: shutil.disk_usage(path).free/GIB for name,path in
            [('host','/mnt/d'),('source','/mnt/wsl/evox'),('output','/mnt/wsl/build')]}

def check_capacity(ready):
    limits = ready.get('minimum_start_gib', {})
    if set(limits) != {'host','source','output'} or any(float(x)<=0 for x in limits.values()):
        raise RuntimeError('Reviewed numeric minimum_start_gib for host/source/output required')
    emergency = ready.get('emergency_minimum_gib', {'host':10,'source':2,'output':2})
    if set(emergency) != {'host','source','output'} or float(emergency['host']) < 10:
        raise RuntimeError('Emergency capacity guards missing/below host 10 GiB')
    current = space()
    for name in limits:
        if current[name] < float(limits[name]) or float(limits[name]) <= float(emergency[name]):
            raise RuntimeError('Insufficient projected '+name+' headroom')
    return current, emergency

def readiness(path):
    ready = json.loads(path.read_text())
    if ready.get('approved') is not True or ready.get('runtime_unvalidated') is not True:
        raise RuntimeError('Readiness approval and runtime_unvalidated required')
    if ready.get('target') != 'lineage_klimt-cp2a-user':
        raise RuntimeError('Readiness target mismatch')
    checks = ready.get('checks', [])
    if not checks or any(c.get('pass') is not True for c in checks):
        raise RuntimeError('All readiness checks must explicitly pass')
    snapshot = wsl_path(ready['snapshot'])
    if sha(snapshot) != ready['sha256']:
        raise RuntimeError('Frozen snapshot hash mismatch')
    heads = manifest_heads(snapshot.read_bytes())
    if ready.get('reviewed_project_heads') != heads:
        raise RuntimeError('reviewed_project_heads must cover the full frozen manifest')
    excluded = ready.get('excluded_heads', {})
    required = {'kernel/xiaomi/klimt','kernel/xiaomi/klimt-prebuilt','vendor/xiaomi/klimt','hardware/xiaomi','device/mediatek/sepolicy_vndr'}
    if not required <= set(excluded) or any(heads.get(p) != v for p,v in excluded.items()):
        raise RuntimeError('Excluded HEAD protection missing/mismatched')
    live_heads(heads)
    if not (S/'out').is_symlink() or (S/'out').resolve() != O:
        raise RuntimeError('Expected shared incremental out symlink absent')
    for path in ('/mnt/wsl/evox','/mnt/wsl/build'):
        if subprocess.run(['mountpoint','-q',path]).returncode:
            raise RuntimeError('Required ext4 disk is not mounted: '+path)
    if not (S/'vendor/evolution-priv/keys/platform.x509.pem').is_file():
        raise RuntimeError('Existing signing certificate missing')
    certificates = ready.get('public_certificate_sha256', {})
    required_certs = {'platform','releasekey','shared','media','networkstack'}
    if set(certificates) != required_certs:
        raise RuntimeError('All existing public certificate digests required')
    for name,digest in certificates.items():
        if sha(S/'vendor/evolution-priv/keys'/f'{name}.x509.pem') != digest:
            raise RuntimeError('Existing certificate digest mismatch: '+name)
    current,emergency = check_capacity(ready)
    return ready,heads,current,emergency

def foreign_processes():
    found = []
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():
            continue
        try:
            name = (path/'comm').read_text().strip()
            cmd = (path/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
            # Names only reject competing jobs; they never select processes to kill.
            if name in {'soong_ui','soong_build','ninja','ckati','kati'} or re.search(r'(verify-evox\d+\.sh|cmp-extract-evox\.sh|build\.sh evox\d+)',cmd):
                found.append({'pid':int(path.name),'name':name})
        except (FileNotFoundError,PermissionError):
            pass
    return found

def watchdog(attempt):
    state = json.loads((attempt/'owner.json').read_text())
    owner = state['build']
    try:
        reason = 'build-process-gone'
        while owned(owner):
            current = space()
            with open(attempt/'disk.jsonl','a') as f:
                f.write(json.dumps(dict(time=time.time(),free_gib=current))+'\n')
            low = [name for name,n in current.items() if n < float(state['emergency'][name])]
            if low:
                reason = 'disk-stop:'+','.join(low)
                write_json(attempt/'disk-stop.json', {'time':time.time(),'free_gib':current,'owner':owner}, True)
                stop_owned(owner)
                break
            time.sleep(15)
        write_json(attempt/'watchdog-terminal.json', {'time':time.time(),'reason':reason}, True)
    except Exception as e:
        write_json(attempt/'watchdog-terminal.json', {'time':time.time(),'reason':'watchdog-error','error':str(e)}, True)
        raise

def record_progress(attempt,owner):
    states=[]
    for path in Path('/proc').iterdir():
        if path.name.isdigit():
            p=proc(int(path.name))
            if p and p['sid']==owner['sid']:
                states.append(p)
    log=attempt/'build.log'
    with open(attempt/'progress.jsonl','a') as f:
        f.write(json.dumps(dict(time=time.time(),processes=states,log_bytes=log.stat().st_size,free_gib=space()))+'\n')

def run(attempt_id,ready_path):
    if not re.fullmatch(r'evox16-attempt\d{2,}',attempt_id):
        raise RuntimeError('Attempt must be evox16-attemptNN')
    source_lock=lock(L/'source.lock')
    if foreign_processes():
        raise RuntimeError('Competing build/extraction exists')
    attempt=L/attempt_id
    attempt.mkdir()
    report=C/attempt_id
    debug=D/attempt_id
    report.mkdir(parents=True)
    debug.mkdir(parents=True)
    write_json(attempt/'status.json',{'state':'preflight','time':time.time()})
    owner=None
    try:
        ready,heads,current,emergency=readiness(ready_path)
        shutil.copyfile(ready_path,attempt/'BUILD_READY.json')
        write_json(attempt/'tooling-snapshot.json',tooling_hashes(),True)
        if capture_manifest(attempt/'prebuild.xml') != heads:
            raise RuntimeError('Live resolved manifest does not match frozen snapshot')
        shutil.copyfile(attempt/'prebuild.xml',debug/'prebuild.xml')
        old_zip=dict(size=ZIP.stat().st_size,mtime_ns=ZIP.stat().st_mtime_ns) if ZIP.exists() else None
        started_ns=time.time_ns()
        with open(attempt/'build.log','xb') as log:
            child=subprocess.Popen(['bash',str(B/'build.sh')],cwd=S,stdout=log,stderr=subprocess.STDOUT,
                                   start_new_session=True,pass_fds=(source_lock.fileno(),),
                                   env=dict(os.environ,EVOX16_ATTEMPT=str(attempt)))
        owner=proc(child.pid)
        if not owner:
            raise RuntimeError('Build wrapper exited before process identity capture')
        state=dict(attempt=attempt_id,build=owner,controller=proc(os.getpid()),started_ns=started_ns,
                   old_zip=old_zip,initial_free_gib=current,emergency=emergency)
        write_json(attempt/'owner.json',state,True)
        with open(attempt/'watchdog.log','xb') as watch_log:
            watch=subprocess.Popen([sys.executable,'-B',str(B/'controller.py'),'watchdog',str(attempt)],
                stdout=watch_log,stderr=subprocess.STDOUT,start_new_session=True,pass_fds=(source_lock.fileno(),))
        write_json(attempt/'status.json',{'state':'building','time':time.time(),'owner':owner})
        while child.poll() is None:
            record_progress(attempt,owner)
            if watch.poll() is not None and owned(owner):
                stop_owned(owner)
                raise RuntimeError('Watchdog terminated unexpectedly; owned attempt stopped')
            time.sleep(15)
        rc=child.wait()
        if not (attempt/'build-exit.json').exists():
            write_json(attempt/'build-exit.json',{'exit':rc,'time':time.time()},True)
        watch.wait(timeout=35)
        if rc != 0:
            write_json(attempt/'status.json',{'state':'build-failed','exit':rc,'time':time.time()})
            return rc if rc>0 else 1
        if capture_manifest(attempt/'postbuild.xml') != heads:
            raise RuntimeError('Source manifest changed during compilation')
        live_heads(heads)
        shutil.copyfile(attempt/'postbuild.xml',debug/'postbuild.xml')
        if not ZIP.is_file() or ZIP.stat().st_mtime_ns < started_ns:
            raise RuntimeError('ZIP not produced by this attempt')
        if old_zip and ZIP.stat().st_mtime_ns==old_zip['mtime_ns']:
            raise RuntimeError('Stale ZIP unchanged from prebuild')
        write_json(attempt/'status.json',{'state':'verifying','time':time.time()})
        require_tooling_frozen(attempt)
        with open(attempt/'verify.log','xb') as verify_log:
            subprocess.run([sys.executable,'-B',str(B/'verify.py'),str(attempt)],cwd=S,
                stdout=verify_log,stderr=subprocess.STDOUT,check=True,pass_fds=(source_lock.fileno(),),
                env=dict(os.environ,EVOX_SOURCE_LOCK_FD=str(source_lock.fileno())))
        write_json(attempt/'status.json',{'state':'image-verified-runtime-pending','time':time.time()})
        return 0
    except Exception as e:
        if owner and owned(owner):
            stop_owned(owner)
        write_json(attempt/'tool-error.json',{'error':str(e),'time':time.time()},True)
        write_json(attempt/'status.json',{'state':'tool-failed','error':str(e),'time':time.time()})
        raise
    finally:
        for name in ('status.json','BUILD_READY.json','owner.json','build-exit.json','watchdog-terminal.json','disk-stop.json','tool-error.json'):
            if (attempt/name).exists():
                shutil.copyfile(attempt/name,debug/name)
        source_lock.close()

def resume(attempt):
    # Recovery observes the existing attempt. It never launches a new build.
    monitor_lock=lock(attempt/'monitor.lock')
    state=json.loads((attempt/'owner.json').read_text())
    original=state['controller']
    if owned(original):
        raise RuntimeError('Existing controller still owns this attempt')
    owner=state['build']
    while owned(owner):
        record_progress(attempt,owner)
        time.sleep(15)
    if not (attempt/'build-exit.json').exists():
        write_json(attempt/'status.json',{'state':'wrapper-lost-no-exit-evidence','time':time.time()})
        raise RuntimeError('Build wrapper disappeared without exit evidence; do not verify')
    rc=json.loads((attempt/'build-exit.json').read_text())['exit']
    if rc!=0:
        write_json(attempt/'status.json',{'state':'build-failed','exit':rc,'time':time.time()})
        return 1
    # The watchdog still holds the shared source lock until its terminal record.
    for _ in range(30):
        try:
            source_lock=lock(L/'source.lock')
            break
        except BlockingIOError:
            time.sleep(1)
    else:raise RuntimeError('Source lock is owned; cannot start extraction')
    ready=json.loads((attempt/'BUILD_READY.json').read_text())
    require_tooling_frozen(attempt)
    heads=ready['reviewed_project_heads']
    live_heads(heads)
    if not (attempt/'postbuild.xml').exists():
        if capture_manifest(attempt/'postbuild.xml')!=heads:raise RuntimeError('Postbuild manifest drift')
    if (C/state['attempt']/'VERIFIED.txt').exists():
        print('Attempt already image verified; no extraction started')
        return 0
    # Any partial extraction/report remains evidence requiring diagnosis.
    if (Path('/mnt/wsl/build/compare/evox16')/state['attempt']).exists():
        raise RuntimeError('Partial extraction exists; preserve and diagnose before a separately named recheck')
    with open(attempt/'verify-resumed.log','xb') as log:
        subprocess.run([sys.executable,'-B',str(B/'verify.py'),str(attempt)],cwd=S,stdout=log,stderr=subprocess.STDOUT,check=True,
            pass_fds=(source_lock.fileno(),),env=dict(os.environ,EVOX_SOURCE_LOCK_FD=str(source_lock.fileno())))
    write_json(attempt/'status.json',{'state':'image-verified-runtime-pending','time':time.time(),'supervisor_resumed':True})
    source_lock.close();monitor_lock.close()
    return 0

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['run','resume','watchdog','stop','status'])
    parser.add_argument('attempt')
    parser.add_argument('readiness',nargs='?')
    args=parser.parse_args()
    if args.mode=='run':
        if not args.readiness:
            parser.error('run requires BUILD_READY.json')
        return run(args.attempt,wsl_path(args.readiness))
    attempt=wsl_path(args.attempt)
    if not attempt.is_absolute():
        attempt=L/args.attempt
    if args.mode=='watchdog':
        watchdog(attempt)
    elif args.mode=='resume':
        return resume(attempt)
    elif args.mode=='stop':
        print('owned attempt signalled' if stop_owned(json.loads((attempt/'owner.json').read_text())['build']) else 'no matching live owned process; no signal sent')
    else:
        print((attempt/'status.json').read_text())
    return 0

if __name__=='__main__':
    sys.exit(main())
