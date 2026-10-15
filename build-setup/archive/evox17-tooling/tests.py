#!/usr/bin/env python3
"""Focused ownership/failure/coverage tests; no Android build or verification."""
import ast,importlib.util,json,os
from pathlib import Path
import signal,subprocess,sys,tempfile,time,unittest
from controller import B,proc,owned,stop_owned,lock,manifest_heads,wsl_path,tooling_hashes

spec=importlib.util.spec_from_file_location('report_gates',B/'report-gates.py')
gates=importlib.util.module_from_spec(spec);spec.loader.exec_module(gates)

class Ownership(unittest.TestCase):
    def setUp(self):self.child=subprocess.Popen(['sleep','60'],start_new_session=True);self.owner=proc(self.child.pid)
    def tearDown(self):
        if self.child.poll() is None:self.child.kill()
        self.child.wait()
    def test_start_tick_mismatch_does_not_signal(self):
        wrong=dict(self.owner,start=self.owner['start']+1)
        self.assertFalse(stop_owned(wrong,grace=.1));self.assertIsNone(self.child.poll())
    def test_boot_mismatch_does_not_signal(self):
        self.assertFalse(stop_owned(dict(self.owner,boot='different'),grace=.1));self.assertIsNone(self.child.poll())
    def test_owned_group_stops_only_owned_child(self):
        other=subprocess.Popen(['sleep','60'],start_new_session=True)
        try:
            self.assertTrue(stop_owned(self.owner,grace=.2));self.child.wait(timeout=2)
            self.assertIsNone(other.poll())
        finally:other.kill();other.wait()
    def test_finished_wrapper_is_not_owned(self):
        self.child.terminate();self.child.wait();self.assertFalse(owned(self.owner));self.assertFalse(stop_owned(self.owner,grace=.1))
    def test_session_mismatch_does_not_signal(self):
        self.assertFalse(stop_owned(dict(self.owner,sid=self.owner['sid']+1),grace=.1))
    def test_leader_exit_with_term_resistant_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker=Path(tmp)/'child.pid'
            code='import os,signal,time; p=os.fork(); '+\
                'signal.signal(signal.SIGTERM,signal.SIG_IGN) if p==0 else None; '+\
                f'open({str(marker)!r},"w").write(str(os.getpid())) if p==0 else None; '+\
                'time.sleep(60)'
            leader=subprocess.Popen([sys.executable,'-c',code],start_new_session=True)
            unrelated=subprocess.Popen(['sleep','60'],start_new_session=True)
            try:
                deadline=time.monotonic()+2
                while not marker.exists() and time.monotonic()<deadline:time.sleep(.01)
                resistant_pid=int(marker.read_text());resistant=proc(resistant_pid)
                self.assertTrue(stop_owned(proc(leader.pid),grace=.2))
                leader.wait(timeout=2)
                deadline=time.monotonic()+2
                while owned(resistant) and time.monotonic()<deadline:time.sleep(.01)
                self.assertFalse(owned(resistant))
                self.assertIsNone(unrelated.poll())
            finally:
                if leader.poll() is None:leader.kill();leader.wait()
                if marker.exists():
                    p=int(marker.read_text())
                    if proc(p):os.kill(p,signal.SIGKILL)
                unrelated.kill();unrelated.wait()

class Gates(unittest.TestCase):
    def test_duplicate_manifest_rejected(self):
        with self.assertRaises(RuntimeError):manifest_heads(b'<manifest><project name="x" revision="'+b'a'*40+b'"/><project name="x" revision="'+b'a'*40+b'"/></manifest>')
    def test_branch_manifest_rejected(self):
        with self.assertRaises(RuntimeError):manifest_heads(b'<manifest><project name="x" revision="cnb"/></manifest>')
    def test_windows_path_conversion(self):self.assertEqual(str(wsl_path('C:\\XiaomiBuilds\\x.json')),'/mnt/c/XiaomiBuilds/x.json')
    def test_lock_excludes_second_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            first=lock(Path(tmp)/'lock')
            try:
                with self.assertRaises(BlockingIOError):lock(Path(tmp)/'lock')
            finally:first.close()
    def test_watchdog_exits_if_wrapper_gone(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            (p/'owner.json').write_text(json.dumps({'build':dict(pid=99999999,pgrp=99999999,sid=99999999,start=1,boot='invalid'),'emergency':{'host':10,'source':2,'output':2}}))
            subprocess.run([sys.executable,'-B',str(B/'controller.py'),'watchdog',str(p)],check=True,timeout=2)
            self.assertEqual(json.loads((p/'watchdog-terminal.json').read_text())['reason'],'build-process-gone')
    def fixture(self,p):
        old=Path('/mnt/c/XiaomiBuilds/compare/evox15')
        (p/'raw-musthold.txt').write_bytes((old/'raw-musthold.txt').read_bytes())
        (p/'raw-extract.txt').write_bytes((old/'raw-extract.txt').read_bytes())
        f=(old/'raw-fixcheck15.txt').read_text().replace('FAIL ','OK   ').replace('evox15 ','retained HIS/Health ')
        (p/'raw-fixcheck.txt').write_text(f)
    def test_semantic_report_fixture_accepts_exact_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);self.fixture(p);self.assertEqual(gates.validate(p)['musthold'],'pass')
    def test_report_new_failure_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);self.fixture(p)
            f=p/'raw-fixcheck.txt';f.write_text(f.read_text().replace('OK   touchfeature props labelled','FAIL touchfeature props labelled'))
            with self.assertRaises(ValueError):gates.validate(p)
    def test_report_missing_check_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);self.fixture(p)
            f=p/'raw-fixcheck.txt';f.write_text('\n'.join(l for l in f.read_text().splitlines() if not l.startswith('OK   touchfeature props labelled')))
            with self.assertRaises(ValueError):gates.validate(p)
    def test_report_wrong_unresolved_symbol_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);self.fixture(p)
            f=p/'raw-musthold.txt';f.write_text(f.read_text().replace('mtk_drm_gateic_set_backlight','unknown_symbol'))
            with self.assertRaises(ValueError):gates.validate(p)
    def test_all_syntax(self):
        for f in B.rglob('*.sh'):subprocess.run(['bash','-n',str(f)],check=True)
        for f in B.glob('*.py'):ast.parse(f.read_text(),filename=str(f))
    def test_generated_flash_wrapper_exact_product_without_fastboot(self):
        from verify import future_flash_scripts
        # Generate only; execute solely the PowerShell product-check line.
        fixture=Path('/mnt/c/Users/diogo/Documents/Codex/2026-10-14/ru/work/tooling/flash-fixture')
        fixture.mkdir(exist_ok=True)
        files=future_flash_scripts(fixture,fixture/'lineage_klimt-evox17-attempt00-img.zip','a'*64)
        subprocess.run(['bash','-n',str(files[0])],check=True)
        command=next(l for l in files[1].read_text().splitlines() if l.startswith('powershell.exe') and 'product-check.txt' in l)
        batch=fixture/'product-check-only.bat'
        batch.write_text('@echo off\r\n'+command+'\r\nexit /b %errorlevel%\r\n',newline='')
        for text,expected in [('product: klimt\n',0),('(bootloader) product: klimt\n',0),('product: klimtExtra\n',2),('product: different\n',2)]:
            (fixture/'product-check.txt').write_text(text)
            result=subprocess.run(['/mnt/c/Windows/System32/cmd.exe','/d','/c',str(batch.name)],cwd=fixture,capture_output=True,text=True)
            self.assertEqual(result.returncode,expected,result.stdout+result.stderr)
    def test_recheck_binding_rejects_changed_source_or_tooling(self):
        from verify import review_binding
        review=dict(approved=True,attempt='evox17-attempt01',source_snapshot_sha256='a'*64,evidence='independent reviewer',tooling_sha256=tooling_hashes())
        review_binding(review,'evox17-attempt01','a'*64)
        for changed in [dict(review,approved=False),dict(review,attempt='evox17-attempt02'),dict(review,source_snapshot_sha256='b'*64),dict(review,tooling_sha256={}),dict(review,evidence='')]:
            with self.assertRaises(RuntimeError):review_binding(changed,'evox17-attempt01','a'*64)

if __name__=='__main__':unittest.main(verbosity=2)
