#!/usr/bin/env python3
"""Foreground startup handshake for an independently detached controller."""
import argparse,json,os
from pathlib import Path
import subprocess,sys,time
import paths
from controller import B,L,D,BUILD,proc,owned,write_json,wsl_path

def spawn_handshake(argv,status_path,log_path,owner_path,result_path,states,timeout=25):
    if status_path.parent.exists():raise RuntimeError('Attempt already exists; choose a fresh ID')
    log_path.parent.mkdir(parents=True,exist_ok=True)
    # Establish redirection before fork/exec. Popen does setsid in its child and
    # waits for exec success before returning; no asynchronous shell & race.
    with open(log_path,'xb') as log:
        child=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
                               start_new_session=True,close_fds=True,env=dict(os.environ,KLIMT_BUILD=BUILD))
    owner=proc(child.pid)
    result=dict(command=argv,reported_pid=child.pid,log=str(log_path),status_path=str(status_path),time=time.time())
    if not owner:
        result.update(state='controller-exited-before-handshake',exit=child.poll())
        write_json(result_path,result,True);return result
    if owner['pid']!=owner['sid'] or owner['pid']!=owner['pgrp']:
        raise RuntimeError('Controller did not establish an independent session')
    write_json(owner_path,dict(controller=owner,command=argv,log=str(log_path),time=time.time()),True)
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if child.poll() is not None or not owned(owner):
            result.update(state='controller-exited-during-handshake',exit=child.poll(),controller=owner)
            write_json(result_path,result,True);return result
        try:
            status=json.loads(status_path.read_text())
        except (FileNotFoundError,json.JSONDecodeError):
            status=None
        if status and status.get('state') in states:
            actual=Path(f'/proc/{child.pid}/fd/1').stat();expected=log_path.stat()
            if (actual.st_dev,actual.st_ino)!=(expected.st_dev,expected.st_ino):
                raise RuntimeError('Controller stdout is not its exclusively opened launch log')
            if not owned(owner):continue
            result.update(state='startup-confirmed',controller=owner,initial_status=status,
                          independent_session=True,log_fd_verified=True,time=time.time())
            write_json(result_path,result,True);return result
        if status and status.get('state') in {'tool-failed','build-failed','compile-failed','tool-failed-resume'}:
            result.update(state='controller-initialization-failed',controller=owner,initial_status=status)
            write_json(result_path,result,True);return result
        time.sleep(.1)
    # Preserve a live unconfirmed controller; do not silently kill it or relaunch.
    result.update(state='startup-unconfirmed-timeout',controller=owner,controller_still_owned=owned(owner))
    write_json(result_path,result,True);return result

def main():
    parser=argparse.ArgumentParser()
    # evox17 has no focused precheck: its module goals installed files into the image staging.
    parser.add_argument('mode',choices=['build']);parser.add_argument('attempt');parser.add_argument('ready')
    args=parser.parse_args()
    import re
    if paths.build_of(args.attempt)!=BUILD:parser.error('Attempt ID does not match KLIMT_BUILD='+BUILD)
    ready=wsl_path(args.ready)
    if not ready.is_file():parser.error('Readiness input file is absent')
    script='controller.py'
    states={'preflight','building'}
    result=spawn_handshake([sys.executable,'-B',str(B/script),'run',args.attempt,str(ready)],
        L/args.attempt/'status.json',L/(args.attempt+'.launch.log'),L/(args.attempt+'.launch-owner.json'),
        L/(args.attempt+'.launch-result.json'),states)
    evidence=D/'launches';evidence.mkdir(parents=True,exist_ok=True)
    write_json(evidence/(args.attempt+'.launch-result.json'),result,True)
    print(json.dumps(result,indent=2))
    return 0 if result['state']=='startup-confirmed' else 1

if __name__=='__main__':sys.exit(main())
