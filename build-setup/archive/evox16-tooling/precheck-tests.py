#!/usr/bin/env python3
"""Focused contract/process tests using harmless fake workers; never invokes m."""
import ast
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import precheck as P
from controller import lock,sha

def contract():
    return dict(approved=True,approval_scope=P.SCOPE,target='lineage_klimt-cp2a-user',runtime_unvalidated=True,
        static_checks=[dict(name='reviewed frozen source',pass_=True,evidence='fixture static review')],
        modules=['KlimtTouchBridge','libudfpshandler'],pending_module_gates=[dict(name='focused module compiler group',status='pending')])

def ready():
    r=contract();r['static_checks'][0]['pass']=r['static_checks'][0].pop('pass_');return r

class Contract(unittest.TestCase):
    def test_precheck_uses_exact_fixed_module_list(self):
        r=ready();self.assertEqual(P.compile_argv(r),['bash',str(P.B/'precheck-build.sh'),'KlimtTouchBridge','libudfpshandler'])
    def test_wrong_scope_or_unapproved_input_rejected(self):
        for change in [dict(approved=False),dict(approval_scope='evox16-p8-full-build'),dict(target='lineage_klimt-cp2a-userdebug')]:
            r=ready();r.update(change)
            with self.assertRaises(RuntimeError):P.validate_static_contract(r)
    def test_full_ready_or_image_fields_rejected(self):
        for key,value in [('checks',[dict(name='P8 approved',pass_=True)]),('image_checks',[]),('full_build_approved',True)]:
            r=ready();r[key]=value
            with self.assertRaises(RuntimeError):P.validate_static_contract(r)
    def test_module_gate_cannot_be_faked_passed(self):
        r=ready();r['pending_module_gates'][0]['status']='pass'
        with self.assertRaises(RuntimeError):P.validate_static_contract(r)
    def test_unreviewed_static_failure_rejected(self):
        r=ready();r['static_checks'][0]['pass']=False
        with self.assertRaises(RuntimeError):P.validate_static_contract(r)
    def test_full_cleanup_or_shell_targets_rejected(self):
        for name in [*P.FORBIDDEN,'-j99','foo;rm','$(x)','../SystemUI','out/system.img','SystemUI SystemUI']:
            r=ready();r['modules']=[name]
            with self.assertRaises(RuntimeError,msg=name):P.validate_static_contract(r)
    def test_empty_duplicate_or_nonstring_targets_rejected(self):
        for modules in [[],['SystemUI','SystemUI'],[{}]]:
            r=ready();r['modules']=modules
            with self.assertRaises(RuntimeError):P.validate_static_contract(r)
    def test_syntax_and_no_verifier_invocation_path(self):
        root=P.B
        for name in ['precheck-build.sh','start-precheck.sh']:subprocess.run(['bash','-n',str(root/name)],check=True)
        source=(root/'precheck.py').read_text();tree=ast.parse(source)
        self.assertNotIn('verify.py',source)
        self.assertNotIn('VERIFIED.txt',source)
        self.assertFalse(any(isinstance(n,(ast.Import,ast.ImportFrom)) and getattr(n,'module',None)=='verify' for n in ast.walk(tree)))
        self.assertEqual(P.watchdog_argv(Path('/fake/attempt'))[-2:],['watchdog','/fake/attempt'])

class Supervisor(unittest.TestCase):
    def setUp(self):
        fixture=Path('/mnt/c/Users/diogo/Documents/Codex/2026-10-14/ru/work/tooling/precheck-fixtures')
        fixture.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=fixture)
        self.base=Path(self.temp.name);self.logs=self.base/'logs';self.debug=self.base/'debug'
        self.logs.mkdir();self.debug.mkdir()
        self.input=self.base/'PRECHECK_READY.json';self.input.write_text(json.dumps(ready()))
        self.real_sleep=time.sleep
        self.patches=[patch.object(P,'L',self.logs),patch.object(P,'D',self.debug),
            patch.object(P,'precheck_readiness',return_value=(ready(),{'fixture':'a'*40},{'host':100,'source':50,'output':100},{'host':10,'source':2,'output':2})),
            patch.object(P,'capture_manifest',side_effect=self.manifest),patch.object(P,'live_heads'),
            patch.object(P,'require_tooling_frozen'),patch.object(P,'foreign_processes',return_value=[]),
            patch.object(P,'progress'),patch.object(P.time,'sleep',side_effect=lambda _seconds:self.real_sleep(.02))]
        for p in self.patches:p.start()
        self.invocations=[]
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()
    def manifest(self,dest):
        dest.write_text('<manifest><project name="fixture" revision="'+'a'*40+'"/></manifest>')
        return {'fixture':'a'*40}
    def fake_compile(self,rc):
        argv=[sys.executable,'-c',f'import time;time.sleep(.2);raise SystemExit({rc})']
        self.invocations.append(argv);return argv
    def fake_watchdog(self,attempt):
        # It observes only the harmless fake compile worker in the test fixture.
        code=f'''import json,sys,time
from pathlib import Path
sys.path.insert(0,{str(P.B)!r})
from controller import owned
p=Path({str(attempt)!r})
owner=json.loads((p/'owner.json').read_text())['build']
while owned(owner):time.sleep(.01)
(p/'watchdog-terminal.json').write_text(json.dumps({{'reason':'build-process-gone'}}))
'''
        argv=[sys.executable,'-B','-c',code];self.invocations.append(argv);return argv
    def execute(self,rc,attempt_id='evox16-precheck01'):
        with patch.object(P,'compile_argv',side_effect=lambda r:self.fake_compile(rc)),patch.object(P,'watchdog_argv',side_effect=self.fake_watchdog):
            return P.run(attempt_id,self.input)
    def test_success_has_source_exit_evidence_without_image_or_p8_claim(self):
        self.assertEqual(self.execute(0),0)
        attempt=self.logs/'evox16-precheck01';result=json.loads((attempt/'RESULTS.json').read_text())
        self.assertTrue(result['compile_group_exit_zero']);self.assertTrue(result['source_identity_unchanged'])
        self.assertFalse(result['image_verification_performed']);self.assertFalse(result['full_build_approval_issued'])
        self.assertEqual(result['pending_module_gates'][0]['status'],'pending')
        self.assertTrue((attempt/'precheck-before.xml').exists());self.assertTrue((attempt/'precheck-after.xml').exists())
        self.assertTrue((self.debug/'evox16-precheck01/precheck-exit.json').exists())
        self.assertFalse(list(self.base.rglob('VERIFIED.txt')))
        self.assertFalse(any('verify.py' in ' '.join(argv) or 'updatepackage' in argv for argv in self.invocations))
    def test_compile_failure_keeps_exit_and_both_source_snapshots(self):
        self.assertEqual(self.execute(17),1)
        attempt=self.logs/'evox16-precheck01'
        self.assertEqual(json.loads((attempt/'precheck-exit.json').read_text())['exit'],17)
        self.assertEqual(json.loads((attempt/'status.json').read_text())['state'],'compile-failed')
        self.assertFalse(json.loads((attempt/'RESULTS.json').read_text())['compile_group_exit_zero'])
        self.assertTrue((attempt/'precheck-before.xml').exists());self.assertTrue((attempt/'precheck-after.xml').exists())
    def test_precheck_conflicts_with_full_build_source_lock(self):
        f=lock(self.logs/'source.lock')
        try:
            with self.assertRaises(BlockingIOError):self.execute(0)
            self.assertFalse((self.logs/'evox16-precheck01').exists());self.assertEqual(self.invocations,[])
        finally:f.close()
    def test_duplicate_attempt_preserves_existing_status(self):
        self.assertEqual(self.execute(0),0)
        status=self.logs/'evox16-precheck01/status.json';before=status.read_bytes()
        with self.assertRaises(FileExistsError):self.execute(0)
        self.assertEqual(status.read_bytes(),before)
        self.assertFalse((self.logs/'evox16-precheck01/tool-error.json').exists())
    def test_source_drift_is_a_separate_tool_failure_with_compile_exit(self):
        def changed(dest):
            self.manifest(dest)
            return {'fixture':('b' if dest.name=='precheck-after.xml' else 'a')*40}
        with patch.object(P,'capture_manifest',side_effect=changed):
            with self.assertRaisesRegex(RuntimeError,'manifest changed'):self.execute(0)
        attempt=self.logs/'evox16-precheck01'
        self.assertEqual(json.loads((attempt/'precheck-exit.json').read_text())['exit'],0)
        self.assertEqual(json.loads((attempt/'status.json').read_text())['state'],'tool-failed')
        self.assertTrue((attempt/'tool-error.json').exists());self.assertFalse((attempt/'RESULTS.json').exists())
    def test_resume_finalized_precheck_never_restarts_workers(self):
        self.assertEqual(self.execute(0),0)
        attempt=self.logs/'evox16-precheck01'
        state=json.loads((attempt/'owner.json').read_text())
        state['controller']=dict(pid=99999999,pgrp=99999999,sid=99999999,start=1,boot='invalid')
        (attempt/'owner.json').write_text(json.dumps(state))
        before=len(self.invocations)
        with patch.object(P,'compile_argv',side_effect=AssertionError('unexpected compile restart')),patch.object(P,'watchdog_argv',side_effect=AssertionError('unexpected watchdog restart')):
            self.assertEqual(P.resume(attempt),0)
        self.assertEqual(len(self.invocations),before)
    def test_missing_exit_on_resume_preserves_failure_evidence(self):
        self.assertEqual(self.execute(0),0)
        attempt=self.logs/'evox16-precheck01'
        state=json.loads((attempt/'owner.json').read_text())
        state['controller']=dict(pid=99999999,pgrp=99999999,sid=99999999,start=1,boot='invalid')
        (attempt/'owner.json').write_text(json.dumps(state))
        (attempt/'precheck-exit.json').unlink()
        with self.assertRaisesRegex(RuntimeError,'without exit evidence'):P.resume(attempt)
        self.assertEqual(json.loads((attempt/'status.json').read_text())['state'],'wrapper-lost-no-exit-evidence')
        self.assertTrue(list(attempt.glob('precheck-resume-error.*.json')))

if __name__=='__main__':unittest.main(verbosity=2)
