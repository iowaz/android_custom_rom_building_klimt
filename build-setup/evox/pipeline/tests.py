#!/usr/bin/env python3
"""Focused ownership/failure/coverage tests; no Android build or verification."""
import ast,hashlib,importlib.util,json,os,re
os.environ.setdefault('KLIMT_BUILD','evox99')
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
                while (not marker.exists() or not marker.read_text().strip()) and time.monotonic()<deadline:time.sleep(.01)
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
        old=B/'test-fixtures/evox15'  # copies of the evox15 verifier reports, carried forward to the current gate
        kernel=('Linux version 6.6.142-android15-8-klimt-4k (build-user@build-host)',
                'Linux version 6.6.142-android15-8 (android-build@r-06b84ad74750c689-xc7u)')  # evox20 kernel string
        (p/'raw-musthold.txt').write_text((old/'raw-musthold.txt').read_text().replace(*kernel))
        (p/'raw-extract.txt').write_bytes((old/'raw-extract.txt').read_bytes())
        f=(old/'raw-fixcheck15.txt').read_text().replace('FAIL ','OK   ').replace('evox15 ','retained HIS/Health ')
        f=f.replace('ro.build.fingerprint = bluejay canary','ro.build.fingerprint matches the selected build reference')
        f=f.replace('vendor SPL unchanged 2026-02-01','vendor SPL matches the selected build reference')
        f=f.replace('OK   system SPL 2026-10-01\n','OK   system SPL 2026-10-05\n')  # evox20 moved the system SPL
        if not f.endswith('\n'):f+='\n'
        have={re.sub(r'\([0-9a-f]{16}\)','(certificate)',l[5:].strip()) for l in f.splitlines() if l.startswith('OK   ')}
        f+=''.join('OK   '+n+'\n' for n in json.loads((B/'expected-legacy-checks.json').read_text()) if n not in have)  # checks added since evox15
        (p/'raw-fixcheck.txt').write_text(f)
    def test_semantic_report_fixture_accepts_exact_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);self.fixture(p);self.assertEqual(gates.validate(p,'evox25')['musthold'],'pass')
    def test_report_new_failure_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);self.fixture(p)
            f=p/'raw-fixcheck.txt';f.write_text(f.read_text().replace('OK   touchfeature props labelled','FAIL touchfeature props labelled'))
            with self.assertRaises(ValueError):gates.validate(p,'evox25')
    def test_report_missing_check_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);self.fixture(p)
            f=p/'raw-fixcheck.txt';f.write_text('\n'.join(l for l in f.read_text().splitlines() if not l.startswith('OK   touchfeature props labelled')))
            with self.assertRaises(ValueError):gates.validate(p,'evox25')
    def test_report_wrong_unresolved_symbol_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);self.fixture(p)
            f=p/'raw-musthold.txt';f.write_text(f.read_text().replace('mtk_drm_gateic_set_backlight','unknown_symbol'))
            with self.assertRaises(ValueError):gates.validate(p,'evox25')
    def test_report_old_kernel_suffix_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);self.fixture(p)
            f=p/'raw-musthold.txt';f.write_text(f.read_text().replace('6.6.142-android15-8 (android-build@','6.6.142-android15-8-klimt-4k (android-build@'))
            with self.assertRaises(ValueError):gates.validate(p,'evox25')
    def test_report_old_kernel_builder_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);self.fixture(p)
            f=p/'raw-musthold.txt';f.write_text(f.read_text().replace('(android-build@','(build-user@'))
            with self.assertRaises(ValueError):gates.validate(p,'evox25')
    def evox26_fixture(self,p):
        self.fixture(p)
        f=p/'raw-musthold.txt'
        banner='Linux version 6.6.142-android15-8-gf6a5b29f9fe5-ab26 (builder@pangu-build-component-system-247-r6kfm) (test compiler) #1 SMP PREEMPT Thu Aug 6 00:00:00 UTC 2026'
        f.write_text(re.sub(r'^Linux version .*$',lambda m:banner,f.read_text(),flags=re.M))
    def test_evox26_accepts_exact_kernel_and_all_194_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);self.evox26_fixture(p)
            result=gates.validate(p,'evox26')
            self.assertEqual(len(result['checks']),194)
            self.assertEqual(result['musthold'],'pass')
            self.assertEqual(gates.validate(p,'evox026')['musthold'],'pass')
    def test_evox26_rejects_wrong_kernel_identity_and_duplicate_banner(self):
        for old,new in [('gf6a5b29f9fe5-ab26','gf6a5b29f9fe5-ab25'),('builder@','android-build@'),
                        ('pangu-build-component-system-247-r6kfm','other-host'),('Aug 6','Aug 7'),
                        ('#1 SMP','#2 SMP')]:
            with self.subTest(new=new),tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp);self.evox26_fixture(p);f=p/'raw-musthold.txt'
                f.write_text(f.read_text().replace(old,new))
                with self.assertRaises(ValueError):gates.validate(p,'evox26')
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);self.evox26_fixture(p);f=p/'raw-musthold.txt'
            f.write_text(f.read_text()+next(l for l in f.read_text().splitlines() if l.startswith('Linux version '))+'\n')
            with self.assertRaises(ValueError):gates.validate(p,'evox26')
    def test_kernel_label_follows_the_build_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);self.evox26_fixture(p);f=p/'raw-musthold.txt'
            with self.assertRaises(ValueError):gates.validate(p,'evox27')
            f.write_text(f.read_text().replace('gf6a5b29f9fe5-ab26','gf6a5b29f9fe5-ab27'))
            self.assertEqual(gates.validate(p,'evox27')['musthold'],'pass')
            with self.assertRaises(ValueError):gates.validate(p,'evox26')
    def test_super_empty_readonly_layout_only_from_evox27(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);self.evox26_fixture(p);f=p/'raw-musthold.txt'
            text=f.read_text().replace('gf6a5b29f9fe5-ab26','gf6a5b29f9fe5-ab27')
            f.write_text(text)
            self.assertEqual(gates.validate(p,'evox27')['musthold'],'pass')
            for ref in ('author','build9'):
                text=text.replace(f'super_empty: IDENTICAL to {ref}\n',f'super_empty: SAME LAYOUT as {ref}, every partition readonly (build/make 90d0063)\n')
            f.write_text(text)
            self.assertEqual(gates.validate(p,'evox27')['musthold'],'pass')
            f.write_text(text.replace('gf6a5b29f9fe5-ab27','gf6a5b29f9fe5-ab26'))
            with self.assertRaises(ValueError):gates.validate(p,'evox26')
            f.write_text(text.replace('super_empty: SAME LAYOUT as build9','super_empty: OTHER LAYOUT as build9'))
            with self.assertRaises(ValueError):gates.validate(p,'evox27')
    def test_kernel_profiles_do_not_accept_each_other(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);self.fixture(p)
            with self.assertRaises(ValueError):gates.validate(p,'evox26')
            self.evox26_fixture(p)
            with self.assertRaises(ValueError):gates.validate(p,'evox25')
            with self.assertRaises(ValueError):gates.validate(p,'invalid')
    def test_evox26_still_rejects_missing_and_failed_historical_checks(self):
        for mutation in ['missing','failed','crc']:
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp);self.evox26_fixture(p)
                f=p/('raw-musthold.txt' if mutation=='crc' else 'raw-fixcheck.txt')
                content=f.read_text()
                if mutation=='missing':content='\n'.join(l for l in content.splitlines() if l!='OK   touchfeature props labelled')
                elif mutation=='failed':content=content.replace('OK   touchfeature props labelled','FAIL touchfeature props labelled')
                else:content=content.replace('CRC MISMATCHES vs kernel 0','CRC MISMATCHES vs kernel 1')
                f.write_text(content)
                with self.assertRaises(ValueError):gates.validate(p,'evox26')
    def test_metadata_reference_checks_both_profiles_and_rejects_stale_values(self):
        helper=B/'legacy/metadata-reference.sh'
        values={
            'evox25':('google/bluejay_beta/bluejay:CANARY/ZP11.260918.007/16484274:user/release-keys','2026-02-01'),
            'evox26':('Xiaomi/klimt_global/klimt:17/OS3.3.260806.171839609/OS3.0.335.0.XOSMIXM:user/release-keys','2026-10-05')}
        with tempfile.TemporaryDirectory() as tmp:
            fixture=Path(tmp)/'build.prop'
            for profile in ('evox25','evox26','evox026'):
                for supplied,(fp,spl) in values.items():
                    fixture.write_text(f'ro.build.fingerprint={fp}\nro.vendor.build.security_patch={spl}\n')
                    for check in ('reference_fingerprint','reference_vendor_spl'):
                        result=subprocess.run(['bash','-c','source "$1" || exit; "$2" "$3"','check',str(helper),check,str(fixture)],env=dict(os.environ,KLIMT_BUILD=profile))
                        self.assertEqual(result.returncode,0 if supplied==('evox26' if profile=='evox026' else profile) else 1)
            result=subprocess.run(['bash','-c','source "$1"','check',str(helper)],env=dict(os.environ,KLIMT_BUILD='invalid'),capture_output=True)
            self.assertEqual(result.returncode,2)
    def test_review_hashes_cover_every_changed_verifier_producer(self):
        hashes=tooling_hashes()
        for name in ['legacy/metadata-reference.sh','legacy/fixcheck7.sh','legacy/fixcheck9.sh',
                     'report-gates.py','expected-legacy-checks.json','verify.py']:
            self.assertEqual(hashes[name],hashlib.sha256((B/name).read_bytes()).hexdigest())
    def test_real_legacy_ok_and_source_lines_select_the_metadata_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);scripts=root/'legacy';scripts.mkdir()
            (scripts/'metadata-reference.sh').write_bytes((B/'legacy/metadata-reference.sh').read_bytes())
            system=root/'fs/system/system';vendor=root/'fs/vendor'
            system.mkdir(parents=True);vendor.mkdir(parents=True)
            cases=[('fixcheck7.sh','ro.build.fingerprint matches the selected build reference','ro.build.fingerprint',system/'build.prop',
                    'google/bluejay_beta/bluejay:CANARY/ZP11.260918.007/16484274:user/release-keys',
                    'Xiaomi/klimt_global/klimt:17/OS3.3.260806.171839609/OS3.0.335.0.XOSMIXM:user/release-keys'),
                   ('fixcheck9.sh','vendor SPL matches the selected build reference','ro.vendor.build.security_patch',vendor/'build.prop','2026-02-01','2026-10-05')]
            for name,label,key,prop,old,new in cases:
                original=(B/'legacy'/name).read_text().splitlines()
                lines=[next(l for l in original if l.startswith('ok(){')),
                       next(l for l in original if l.startswith('source ') and 'metadata-reference.sh' in l),
                       next(l for l in original if l.startswith('ok "'+label+'"'))]
                script=scripts/name
                script.write_text('#!/bin/bash\nF="$EVOX_EXTRACT/fs"\n'+'\n'.join(lines)+'\n')
                for profile,want,wrong in [('evox25',old,new),('evox26',new,old)]:
                    for value,passed in [(want,True),(wrong,False),(want+'extra',False)]:
                        prop.write_text(key+'='+value+'\n')
                        result=subprocess.run(['bash',str(script)],env=dict(os.environ,KLIMT_BUILD=profile,EVOX_EXTRACT=str(root)),capture_output=True,text=True)
                        self.assertEqual(result.returncode,0,result.stderr)
                        self.assertEqual(result.stdout.strip(),('OK   ' if passed else 'FAIL ')+label)
    def test_no_module_shadowed_by_a_local(self):
        # verify.py once assigned a local `paths`, which shadowed the paths module inside main() (evox18 recheck01).
        modules={'paths','json','os','re','shutil','subprocess','sys','time','hashlib','zipfile'}
        for f in B.glob('*.py'):
            tree=ast.parse(f.read_text(),filename=str(f))
            for fn in [n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef)]:
                stored={t.id for n in ast.walk(fn) for t in ([n] if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store) else [])}
                self.assertFalse(stored&modules,(f.name,fn.name,stored&modules))
    def test_no_windows_drive_paths(self):
        # The legacy checks once called /mnt/c/XiaomiBuilds/... helpers that moved (evox18 recheck02).
        # Locations come from paths.py (KLIMT_ROOT) or are relative to the script.
        for f in [*B.glob('*.py'),*B.glob('*.sh'),*B.glob('legacy/*.sh'),*B.glob('image-checks/check_image.py')]:
            if f.name in ('tests.py','paths.py'):continue
            for n,line in enumerate(f.read_text().splitlines(),1):
                self.assertNotRegex(line,r'/mnt/[a-z]/(?!android_rom_building)',f'{f.name}:{n}')
    def test_all_syntax(self):
        for f in B.rglob('*.sh'):subprocess.run(['bash','-n',str(f)],check=True)
        for f in B.glob('*.py'):ast.parse(f.read_text(),filename=str(f))
    def test_generated_flash_wrapper_exact_product_without_fastboot(self):
        from verify import future_flash_scripts
        # Generate only; execute solely the PowerShell product-check line.
        import paths
        fixture=paths.ROOT/'diagnostics'/'logs'/'flash-fixture'
        fixture.mkdir(parents=True,exist_ok=True)
        files=future_flash_scripts(fixture,fixture/'lineage_klimt-evox17-attempt00-img.zip','a'*64)
        subprocess.run(['bash','-n',str(files[0])],check=True)
        command=next(l for l in files[1].read_text().splitlines() if l.startswith('powershell.exe') and 'product-check.txt' in l)
        batch=fixture/'product-check-only.bat'
        batch.write_text('@echo off\r\n'+command+'\r\nexit /b %errorlevel%\r\n',newline='')
        for text,expected in [('product: klimt\n',0),('(bootloader) product: klimt\n',0),('product: klimtExtra\n',2),('product: different\n',2)]:
            (fixture/'product-check.txt').write_text(text)
            # Change into the folder and call the batch file by its full path: cmd.exe launched from WSL (or
            # with NoDefaultCurrentDirectoryInExePath set) does not run a .bat from the current folder by name.
            win=subprocess.check_output(['wslpath','-w',str(fixture)],text=True).strip()
            result=subprocess.run(['/mnt/c/Windows/System32/cmd.exe','/d','/c','cd /d '+win+' && '+win+chr(92)+batch.name],cwd=fixture,capture_output=True,text=True)
            self.assertEqual(result.returncode,expected,result.stdout+result.stderr)
    def test_flash_helper_uses_slot_b_and_rejects_wrong_product_or_archive(self):
        from verify import future_flash_scripts
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);archive=p/'lineage_klimt-evox26-img.zip';archive.write_bytes(b'fixture archive')
            marker=p/'VERIFIED.txt';marker.write_text('fixture only')
            script,bat=future_flash_scripts(p,archive,hashlib.sha256(archive.read_bytes()).hexdigest())
            self.assertIn('"%FASTBOOT%" --slot=b update --skip-reboot "'+archive.name+'"',bat.read_text())
            mock=p/'fastboot';log=p/'calls'
            mock.write_text('#!/bin/bash\nif [ "$1" = getvar ]; then printf "%s\\n" "$MOCK_PRODUCT"; exit 0; fi\nprintf "%s\\n" "$@" >> "$MOCK_LOG"\n')
            mock.chmod(0o755)
            env=dict(os.environ,PATH=str(p)+':'+os.environ['PATH'],MOCK_LOG=str(log))
            for product,accepted in [('product: klimt',True),('(bootloader) product: klimt',True),
                                     ('product: klimtExtra',False),('evilproduct: klimt',False),
                                     ('product: other',False),('product: klimt\nproduct: klimt',False)]:
                log.unlink(missing_ok=True)
                result=subprocess.run(['bash',str(script),'--flash'],env=dict(env,MOCK_PRODUCT=product),capture_output=True)
                self.assertEqual(result.returncode==0,accepted,(product,result.stderr))
                self.assertEqual(log.read_text().splitlines() if log.exists() else [],['--slot=b','update','--skip-reboot',archive.name] if accepted else [])
            for defect in ('hash','marker','argument'):
                log.unlink(missing_ok=True);archive.write_bytes(b'bad' if defect=='hash' else b'fixture archive')
                if defect=='marker':marker.unlink()
                else:marker.write_text('fixture only')
                result=subprocess.run(['bash',str(script)]+([] if defect=='argument' else ['--flash']),env=dict(env,MOCK_PRODUCT='product: klimt'),capture_output=True)
                self.assertNotEqual(result.returncode,0)
                self.assertFalse(log.exists())
    def test_recheck_binding_rejects_changed_source_or_tooling(self):
        from verify import review_binding
        review=dict(approved=True,attempt='evox17-attempt01',source_snapshot_sha256='a'*64,evidence='independent reviewer',tooling_sha256=tooling_hashes())
        review_binding(review,'evox17-attempt01','a'*64)
        for changed in [dict(review,approved=False),dict(review,attempt='evox17-attempt02'),dict(review,source_snapshot_sha256='b'*64),dict(review,tooling_sha256={}),dict(review,evidence='')]:
            with self.assertRaises(RuntimeError):review_binding(changed,'evox17-attempt01','a'*64)

if __name__=='__main__':unittest.main(verbosity=2)
