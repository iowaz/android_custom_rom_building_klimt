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
        retired={'klimt_felica may call system_server'}  # 2026-11-05: Mobile FeliCa removed
        f=''.join(l+'\n' for l in f.splitlines() if l[5:].strip() not in retired)
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
    def test_evox26_accepts_exact_kernel_and_all_195_checks(self):
        # 194 until 2026-11-04; three checks of the dropped device/lineage/sepolicy and system/core patches retired.
        # 2026-11-05: the FeliCa policy check replaced by a removal check, plus four for the log-review fixes.
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);self.evox26_fixture(p)
            result=gates.validate(p,'evox26')
            self.assertEqual(len(result['checks']),195)
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
    def test_date_build_kernel_label_and_profile(self):
        # Builds after evox31 are named by date; the kernel ends in -ab<date>[.N] and every evox26+ rule applies.
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);self.evox26_fixture(p);f=p/'raw-musthold.txt'
            for build in ('20261105','20261105.2'):
                f.write_text(re.sub(r'gf6a5b29f9fe5-ab[0-9.]+ ',f'gf6a5b29f9fe5-ab{build} ',f.read_text()))
                self.assertEqual(gates.validate(p,build)['musthold'],'pass')
                for other in ('evox26','evox31','20261106','20261105.3'):
                    with self.assertRaises(ValueError):gates.validate(p,other)
            for invalid in ('20261103','20261105.1','20261131','2026110','evox'):
                with self.assertRaises(ValueError):gates.validate(p,invalid)
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
            for profile in ('evox25','evox26','evox026','20261105','20261105.2'):
                for supplied,(fp,spl) in values.items():
                    fixture.write_text(f'ro.build.fingerprint={fp}\nro.vendor.build.security_patch={spl}\n')
                    for check in ('reference_fingerprint','reference_vendor_spl'):
                        result=subprocess.run(['bash','-c','source "$1" || exit; "$2" "$3"','check',str(helper),check,str(fixture)],env=dict(os.environ,KLIMT_BUILD=profile))
                        self.assertEqual(result.returncode,0 if supplied==('evox25' if profile=='evox25' else 'evox26') else 1)
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
            for helper in ('metadata-reference.sh','build-profile.sh'):(scripts/helper).write_bytes((B/'legacy'/helper).read_bytes())
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
                for profile,want,wrong in [('evox25',old,new),('evox26',new,old),('20261105',new,old)]:
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
        for build in ('evox26','20261105.2'):
            with self.subTest(build=build):self.flash_helper_case(build)
    def flash_helper_case(self,build):
        from verify import future_flash_scripts
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);archive=p/f'lineage_klimt-{build}-img.zip';archive.write_bytes(b'fixture archive')
            marker=p/'VERIFIED.txt';marker.write_text('fixture only')
            script,bat=future_flash_scripts(p,archive,hashlib.sha256(archive.read_bytes()).hexdigest())
            self.assertIn('"%FASTBOOT%" --slot=b update --skip-reboot "'+archive.name+'"',bat.read_text())
            self.assertIn('if not "%errorlevel%"=="0" exit /b 1\n"%FASTBOOT%" reboot\nif not "%errorlevel%"=="0" exit /b 1',bat.read_text())
            mock=p/'fastboot';log=p/'calls'
            mock.write_text('#!/bin/bash\nif [ "$1" = getvar ]; then printf "%s\\n" "$MOCK_PRODUCT"; exit 0; fi\nprintf "%s\\n" "$@" >> "$MOCK_LOG"\n'
                            'if [ "$1" = --slot=b ] && [ -n "$MOCK_UPDATE_EXIT" ]; then exit "$MOCK_UPDATE_EXIT"; fi\n'
                            'if [ "$1" = reboot ] && [ -n "$MOCK_REBOOT_EXIT" ]; then exit "$MOCK_REBOOT_EXIT"; fi\nexit 0\n')
            mock.chmod(0o755)
            env=dict(os.environ,PATH=str(p)+':'+os.environ['PATH'],MOCK_LOG=str(log))
            for product,accepted in [('product: klimt',True),('(bootloader) product: klimt',True),
                                     ('product: klimtExtra',False),('evilproduct: klimt',False),
                                     ('product: other',False),('product: klimt\nproduct: klimt',False)]:
                log.unlink(missing_ok=True)
                result=subprocess.run(['bash',str(script),'--flash'],env=dict(env,MOCK_PRODUCT=product),capture_output=True)
                self.assertEqual(result.returncode==0,accepted,(product,result.stderr))
                self.assertEqual(log.read_text().splitlines() if log.exists() else [],['--slot=b','update','--skip-reboot',archive.name,'reboot'] if accepted else [])
            for update_exit,reboot_exit in [(7,0),(-1,0),(0,9)]:
                log.unlink(missing_ok=True)
                result=subprocess.run(['bash',str(script),'--flash'],env=dict(env,MOCK_PRODUCT='product: klimt',
                    MOCK_UPDATE_EXIT=str(update_exit),MOCK_REBOOT_EXIT=str(reboot_exit)),capture_output=True)
                self.assertNotEqual(result.returncode,0)
                expected=['--slot=b','update','--skip-reboot',archive.name]+([] if update_exit else ['reboot'])
                self.assertEqual(log.read_text().splitlines(),expected)
                self.assertNotIn(b'Update complete.',result.stdout)
            for defect in ('hash','marker','argument'):
                log.unlink(missing_ok=True);archive.write_bytes(b'bad' if defect=='hash' else b'fixture archive')
                if defect=='marker':marker.unlink()
                else:marker.write_text('fixture only')
                result=subprocess.run(['bash',str(script)]+([] if defect=='argument' else ['--flash']),env=dict(env,MOCK_PRODUCT='product: klimt'),capture_output=True)
                self.assertNotEqual(result.returncode,0)
                self.assertFalse(log.exists())
    def test_windows_flash_reboots_only_after_success(self):
        from verify import future_flash_scripts
        import paths
        compiler=Path('/mnt/c/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe')
        if not compiler.is_file():self.skipTest('Windows .NET Framework compiler unavailable')
        parent=paths.ROOT/'diagnostics/logs';parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='flash-reboot-',dir=parent) as tmp:
            root=Path(tmp);dest=root/'output-zips/evox99';dest.mkdir(parents=True)
            tools=root/'tools/platform-tools';tools.mkdir(parents=True)
            executable=tools/'fastboot.exe';source=root/'FakeFastboot.cs';log=root/'calls'
            source.write_text(r'''using System;
using System.IO;
class FakeFastboot {
  static int Main(string[] args) {
    if (args.Length == 0) return 99;
    if (args[0] == "getvar") {
      Console.Error.WriteLine(Environment.GetEnvironmentVariable("MOCK_PRODUCT"));
      return 0;
    }
    File.AppendAllText(Environment.GetEnvironmentVariable("MOCK_LOG"),
      string.Join(" ", args) + Environment.NewLine);
    int code;
    string name = args[0] == "--slot=b" ? "MOCK_UPDATE_EXIT" :
      args[0] == "reboot" ? "MOCK_REBOOT_EXIT" : "";
    return name != "" && int.TryParse(Environment.GetEnvironmentVariable(name), out code) ? code : 99;
  }
}''')
            def win(path):return subprocess.check_output(['wslpath','-w',str(path)],text=True).strip()
            compiled=subprocess.run([str(compiler),'/nologo','/out:'+win(executable),win(source)],capture_output=True)
            self.assertEqual(compiled.returncode,0,compiled.stdout+compiled.stderr)
            self.assertTrue(executable.is_file())
            archive=dest/'lineage_klimt-evox99-img.zip';archive.write_bytes(b'fixture archive')
            (dest/'VERIFIED.txt').write_text('fixture only')
            _,bat=future_flash_scripts(dest,archive,hashlib.sha256(archive.read_bytes()).hexdigest())
            driver=root/'run.bat'
            for name,product,update_exit,reboot_exit in [
                    ('success','product: klimt',0,0),
                    ('update-failed','product: klimt',7,0),
                    ('update-crashed','product: klimt',-1,0),
                    ('reboot-failed','product: klimt',0,9),
                    ('reboot-crashed','product: klimt',0,-1),
                    ('wrong-product','product: different',0,0),
                    ('bad-hash','product: klimt',0,0)]:
                with self.subTest(case=name):
                    log.unlink(missing_ok=True)
                    archive.write_bytes(b'bad' if name=='bad-hash' else b'fixture archive')
                    driver.write_text(f'''@echo off
setlocal
set "PSModulePath=%SystemRoot%\\System32\\WindowsPowerShell\\v1.0\\Modules"
set "MOCK_PRODUCT={product}"
set "MOCK_LOG={win(log)}"
set "MOCK_UPDATE_EXIT={update_exit}"
set "MOCK_REBOOT_EXIT={reboot_exit}"
call "{win(bat)}" /flash
exit /b %errorlevel%
''',newline='\r\n')
                    result=subprocess.run(['/mnt/c/Windows/System32/cmd.exe','/d','/c',win(driver)],capture_output=True)
                    self.assertEqual(result.returncode==0,name=='success',result.stdout+result.stderr)
                    calls=log.read_text().splitlines() if log.exists() else []
                    expected=[] if name in ('wrong-product','bad-hash') else [
                        '--slot=b update --skip-reboot '+archive.name]+([] if update_exit else ['reboot'])
                    self.assertEqual(calls,expected)
                    if name!='success':self.assertNotIn(b'Update complete.',result.stdout)

    def test_recheck_binding_rejects_changed_source_or_tooling(self):
        from verify import review_binding
        review=dict(approved=True,attempt='evox17-attempt01',source_snapshot_sha256='a'*64,evidence='independent reviewer',tooling_sha256=tooling_hashes())
        review_binding(review,'evox17-attempt01','a'*64)
        for changed in [dict(review,approved=False),dict(review,attempt='evox17-attempt02'),dict(review,source_snapshot_sha256='b'*64),dict(review,tooling_sha256={}),dict(review,evidence='')]:
            with self.assertRaises(RuntimeError):review_binding(changed,'evox17-attempt01','a'*64)

class EffectiveHeads(unittest.TestCase):
    """Patched projects (device/xiaomi/klimt/patches/PATCHES.json) are pinned at their base and live at final_head."""
    A,F,X,O='a'*40,'f'*40,'1'*40,'0'*40
    def bundle(self,**extra):
        record=dict(project='frameworks/native',**{'class':'klimt'},purpose='SMPTE guard',base=self.A,base_tree='b'*40,
                    final_tree='c'*40,final_head=self.F,patches=[{'file':'frameworks/native/0001-x.patch','sha256':'d'*64}])
        record.update(extra)
        return [record]
    def frozen(self,native=None):
        return {'device/xiaomi/klimt':self.X,'frameworks/native':native or self.A,'frameworks/base':self.O}
    def test_final_head_accepted_over_its_base(self):
        from controller import parse_patch_bundle,effective_heads
        heads=effective_heads(self.frozen(),parse_patch_bundle(json.dumps(self.bundle())))
        self.assertEqual(heads,{'device/xiaomi/klimt':self.X,'frameworks/native':self.F,'frameworks/base':self.O})
        # `repo manifest -r` reports the live HEAD (final_head), which is what the controller compares with.
        live=manifest_heads(('<manifest>'+''.join(f'<project path="{p}" name="{p}" revision="{h}"/>' for p,h in heads.items())+'</manifest>').encode())
        self.assertEqual(live,heads)
        self.assertNotEqual(live,self.frozen())
    def test_wrong_final_head_base_head_or_unlisted_drift_rejected(self):
        from controller import parse_patch_bundle,effective_heads
        heads=effective_heads(self.frozen(),parse_patch_bundle(json.dumps(self.bundle())))
        for project,live in [('frameworks/native','9'*40),('frameworks/native',self.A),('frameworks/base',self.F)]:
            with self.subTest(project=project,live=live):self.assertNotEqual(dict(heads,**{project:live}),heads)
    def test_base_mismatch_rejected(self):
        from controller import parse_patch_bundle,effective_heads
        bundle=parse_patch_bundle(json.dumps(self.bundle()))
        for pin in (self.F,'9'*40):
            with self.assertRaises(RuntimeError):effective_heads(self.frozen(native=pin),bundle)
    def test_patched_project_missing_from_manifest_rejected(self):
        from controller import parse_patch_bundle,effective_heads
        with self.assertRaises(RuntimeError):effective_heads(self.frozen(),parse_patch_bundle(json.dumps(self.bundle(project='system/core'))))
    def test_without_bundle_frozen_pins_are_the_heads(self):
        from controller import effective_heads
        self.assertEqual(effective_heads(self.frozen(),{}),self.frozen())
    def test_bundle_format_is_strict(self):
        from controller import parse_patch_bundle
        good=self.bundle()[0]
        for bad in [[good,good],[dict(good,**{'class':'other'})],[dict(good,base='cnb')],[dict(good,final_head=self.A)],
                    [dict(good,project='device/xiaomi/klimt')],[dict(good,patches=[])],{'frameworks/native':good},[dict(good,project='')]]:
            with self.subTest(bad=str(bad)[:60]),self.assertRaises(RuntimeError):parse_patch_bundle(json.dumps(bad))
        self.assertEqual(set(parse_patch_bundle(json.dumps([good,dict(good,project='build/make',**{'class':'personal'})]))),{'frameworks/native','build/make'})
    def git_tree(self,root):
        device=root/'device/xiaomi/klimt';(device/'patches').mkdir(parents=True)
        run=lambda *a:subprocess.run(['git','-C',str(device),*a],check=True,capture_output=True,text=True).stdout.strip()
        run('init','-q');run('config','user.email','t@example.invalid');run('config','user.name','t')
        (device/'README').write_text('x\n');run('add','-A');run('commit','-q','-m','no bundle')
        old=run('rev-parse','HEAD')
        (device/'patches/PATCHES.json').write_text(json.dumps(self.bundle()));run('add','-A');run('commit','-q','-m','bundle')
        first=run('rev-parse','HEAD')
        (device/'patches/PATCHES.json').write_text(json.dumps(self.bundle(final_head='e'*40)));run('add','-A');run('commit','-q','-m','re-export')
        return device,old,first,run('rev-parse','HEAD')
    def test_bundle_is_read_at_the_frozen_device_pin(self):
        from controller import patch_bundle,expected_heads,ready_heads
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);device,old,first,second=self.git_tree(root)
            (device/'patches/PATCHES.json').write_text('worktree edits are ignored')
            self.assertEqual(patch_bundle(dict(self.frozen(),**{'device/xiaomi/klimt':first}),root)['frameworks/native']['final_head'],self.F)
            self.assertEqual(expected_heads(dict(self.frozen(),**{'device/xiaomi/klimt':second}),root)['frameworks/native'],'e'*40)
            self.assertEqual(patch_bundle(dict(self.frozen(),**{'device/xiaomi/klimt':old}),root),{})  # evox31 and older
            with self.assertRaises(RuntimeError):patch_bundle(dict(self.frozen(),**{'device/xiaomi/klimt':'9'*40}),root)
            with self.assertRaises(RuntimeError):patch_bundle({'frameworks/native':self.A},root)
            frozen=dict(self.frozen(),**{'device/xiaomi/klimt':first})
            effective=dict(frozen,**{'frameworks/native':self.F})
            self.assertEqual(ready_heads({'reviewed_project_heads':frozen,'effective_project_heads':effective},root),effective)
            for recorded in ({'reviewed_project_heads':frozen},{'reviewed_project_heads':frozen,'effective_project_heads':dict(effective,**{'frameworks/native':'e'*40})}):
                with self.assertRaises(RuntimeError):ready_heads(recorded,root)
            legacy=dict(frozen,**{'device/xiaomi/klimt':old})
            self.assertEqual(ready_heads({'reviewed_project_heads':legacy},root),legacy)

class Readiness(unittest.TestCase):
    def test_apply_check_requires_final_for_exactly_the_bundle(self):
        from ready import bundle_final
        bundle={'frameworks/native':{},'build/soong':{}}
        self.assertTrue(bundle_final(0,'FINAL frameworks/native\nFINAL build/soong\n',bundle))
        self.assertTrue(bundle_final(0,'FINAL: frameworks/native (head f)\n\nFINAL build/soong\n',bundle))
        for rc,out in [(1,'FINAL frameworks/native\nFINAL build/soong\n'),(0,'FINAL frameworks/native\n'),
                       (0,'FINAL frameworks/native\nAPPLIED build/soong\n'),(0,'FINAL frameworks/native\nMISMATCH build/soong\n'),
                       (0,'FINAL frameworks/native\nDIRTY build/soong\n'),(0,'FINAL frameworks/native\nHASH build/soong\n'),
                       (0,'FINAL frameworks/native\nFINAL build/soong\nFINAL system/core\n'),(0,''),
                       (0,'FINAL frameworks/native\nFINAL build/soong\nFINAL build/soong\n'),(0,'FINAL frameworks/native\nFINAL build/soong\nsomething else\n')]:
            with self.subTest(rc=rc,out=out):self.assertFalse(bundle_final(rc,out,bundle))
    def test_every_semantic_purpose_has_a_pipeline_reference_patch(self):
        from ready import PURPOSES,SEMANTIC_PATCHES,reference_patches
        for project,purpose in PURPOSES:
            with self.subTest(purpose=purpose):self.assertTrue(reference_patches(project,purpose,[SEMANTIC_PATCHES]))
        sources=(SEMANTIC_PATCHES/'SOURCES.txt').read_text().splitlines()
        listed={l.split()[1]:l.split()[0] for l in sources if l and not l.startswith('#')}
        self.assertEqual(listed,{str(p.relative_to(SEMANTIC_PATCHES)):hashlib.sha256(p.read_bytes()).hexdigest() for p in SEMANTIC_PATCHES.rglob('*.patch')})
    def test_bulletin_state_counts_pages_and_never_raises(self):
        from ready import bulletin_state
        def fake(url):
            if 'status:open' in url:return ")]}'\n[]\n"
            start=int(url.rsplit('&S=',1)[1])
            if start==0:return ")]}'\n"+json.dumps([{'branch':'lineage-24.0'}]*499+[{'branch':'lineage-23.2','_more_changes':True}])
            return ")]}'\n"+json.dumps([{'branch':'lineage-24.0'}]*3)
        state=bulletin_state('2026-11',fake)
        self.assertEqual((state['topic'],state['open'],state['merged'],state['state']),('C_asb_2026-11',0,503,'merged'))
        self.assertEqual(state['merged_by_branch'],{'lineage-24.0':502,'lineage-23.2':1})
        def down(url):raise OSError('network unreachable')
        self.assertEqual(bulletin_state('2026-11',down)['state'],'unavailable')
        self.assertEqual(bulletin_state('2026-11',lambda url:'[]')['state'],'unavailable')
        self.assertEqual(bulletin_state('2026-12',lambda url:")]}'\n[]")['state'],'not started')
        self.assertEqual(bulletin_state('2026-12',lambda url:")]}'\n[{}]" if 'open' in url else ")]}'\n[]")['state'],'in review')
    def test_security_patch_textproto(self):
        from ready import textproto_value
        self.assertEqual(textproto_value('name: "RELEASE_PLATFORM_SECURITY_PATCH"\nvalue {\n  string_value: "2026-10-01"\n}\n'),'2026-10-01')
        self.assertIsNone(textproto_value('name: "X"\n'))

class DateBuilds(unittest.TestCase):
    def test_build_names(self):
        import paths
        for name in ('evox1','evox31','evox026','20261105','20261105.2','20261105.10','20270101'):
            self.assertTrue(paths.is_build(name),name)
        for name in ('20261103','20261105.1','20261105.02','20261105.','20261131','20261305','2026110','202611050',
                     'evox','evox31-attempt01','20261105-attempt01','klimt',''):
            self.assertFalse(paths.is_build(name),name)
        self.assertEqual([paths.build_of(a) for a in ('evox31-attempt01','20261105-attempt01','20261105.2-attempt12')],['evox31','20261105','20261105.2'])
        for bad in ('20261105.1-attempt01','20261103-attempt01','20261105-attempt1','20261105attempt01'):
            with self.assertRaises(ValueError):paths.build_of(bad)
        self.assertEqual([paths.kernel_label(b) for b in ('evox31','evox026','20261105','20261105.2')],['ab31','ab26','ab20261105','ab20261105.2'])
        self.assertEqual([paths.at_least(b,28) for b in ('evox27','evox28','20261105')],[False,True,True])
        self.assertTrue(paths.is_date_build('20261105') and not paths.is_date_build('evox31'))
    def test_current_build_from_environment(self):
        for value,ok in [('20261105',True),('evox31',True),('20261105.2',True),('20261103',False),('evox',False)]:
            code='import paths;print(paths.current_build())'
            r=subprocess.run([sys.executable,'-B','-c',code],cwd=B,env=dict(os.environ,KLIMT_BUILD=value),capture_output=True,text=True)
            self.assertEqual(r.returncode==0,ok,(value,r.stderr))
    def test_shell_build_profile(self):
        helper=B/'legacy/build-profile.sh'
        for build,label,at26,at28 in [('evox25','ab25',1,1),('evox26','ab26',0,1),('evox28','ab28',0,0),('20261105','ab20261105',0,0),
                                     ('20261105.2','ab20261105.2',0,0),('20261105.1','',1,1),('bogus','',1,1)]:
            r=subprocess.run(['bash','-c','source "$1"; echo "$KERNEL_LABEL"; build_at_least 26; echo $?; build_at_least 28; echo $?','x',str(helper)],
                             env=dict(os.environ,KLIMT_BUILD=build),capture_output=True,text=True)
            self.assertEqual(r.stdout.split('\n')[:3],[label,str(at26),str(at28)],build)
    def test_start_sh_derives_the_build(self):
        text=(B/'start.sh').read_text()
        self.assertIn('${1%%-attempt*}',text)

class Prepare(unittest.TestCase):
    LIVE31='''<?xml version='1.0' encoding='UTF-8'?>
<manifest>
  <include name="default.xml" />
  <remote name="iowaz" fetch="https://github.com/iowaz" />
  <remote name="misakazip" fetch="https://github.com/misakazip-dev" />
  <project name="android_device_xiaomi_klimt" path="device/xiaomi/klimt" remote="iowaz" revision="evox31" upstream="evox31" dest-branch="evox31" />
  <project name="android_kernel_xiaomi_klimt" path="kernel/xiaomi/klimt" remote="iowaz" revision="evox31" upstream="evox31" clone-depth="1" dest-branch="evox31" />
  <project name="android_kernel_xiaomi_klimt-prebuilt" path="kernel/xiaomi/klimt-prebuilt" remote="misakazip" revision="a2d1dae44726c14b1295f4042cddd9fedacd39e0" upstream="17.0" clone-depth="1" />
  <project name="proprietary_vendor_xiaomi_klimt" path="vendor/xiaomi/klimt" remote="iowaz" revision="evox31" upstream="evox31" dest-branch="evox31" />
  <project path="hardware/xiaomi" name="LineageOS/android_hardware_xiaomi" remote="github" revision="lineage-24.0" />
  <project path="device/mediatek/sepolicy_vndr" name="LineageOS/android_device_mediatek_sepolicy_vndr" remote="github" revision="lineage-24.0" />
  <extend-project name="frameworks_native" path="frameworks/native" remote="iowaz" revision="evox31" />
  <extend-project name="system_core" path="system/core" remote="iowaz" revision="evox31" />
</manifest>'''
    METADATA='''# evox31: actual unchanged kernel source f6a5b29f9fe59e4849680d50232f8b5758aa8c11.
# ab31 is this personal ROM build number, not an official Xiaomi CI number.
CONFIG_LOCALVERSION="-android15-8-gf6a5b29f9fe5-ab31"
# CONFIG_LOCALVERSION_AUTO is not set
'''
    def test_previous_build_ordering(self):
        import prepare
        names=['evox9','evox10','evox31','evox26-published','evox15-attempt1','20261105','20261105.2','20261106']
        self.assertEqual(prepare.previous_build('20261105',names),'evox31')
        self.assertEqual(prepare.previous_build('20261105.2',names),'20261105')
        self.assertEqual(prepare.previous_build('20261106',names),'20261105.2')
        self.assertEqual(prepare.previous_build('20261110',names),'20261106')
        self.assertEqual(prepare.previous_build('evox11',names),'evox10')
        with self.assertRaises(ValueError):prepare.previous_build('evox9',names)
        with self.assertRaises(ValueError):prepare.previous_build('20261103',names)
    def test_live_manifest_has_klimt_projects_only(self):
        import prepare
        text=prepare.live_manifest(self.LIVE31)
        root=ET_parse(text)
        self.assertEqual(root.findall('extend-project'),[])
        projects={p.get('path'):p.attrib for p in root.findall('project')}
        self.assertEqual(set(projects),set(prepare.KLIMT))
        self.assertEqual(projects['device/xiaomi/klimt'],{'name':'android_device_xiaomi_klimt','path':'device/xiaomi/klimt','remote':'iowaz','revision':'cnb'})
        old={p.get('path'):p.attrib for p in ET_parse(self.LIVE31).findall('project')}
        for p in ('kernel/xiaomi/klimt','kernel/xiaomi/klimt-prebuilt','vendor/xiaomi/klimt'):self.assertEqual(projects[p],old[p])
        for p in ('hardware/xiaomi','device/mediatek/sepolicy_vndr'):
            self.assertEqual((projects[p]['remote'],projects[p]['revision'],projects[p]['name']),('github','lineage-24.0',old[p]['name']))
        self.assertEqual([i.get('name') for i in root.findall('include')],['default.xml'])
        with self.assertRaises(ValueError):prepare.live_manifest(self.LIVE31.replace('path="vendor/xiaomi/klimt"','path="vendor/other"'))
        with self.assertRaises(ValueError):prepare.live_manifest(self.LIVE31.replace('remote="misakazip" revision','remote="github" revision'))
    def test_github_fetch_fix(self):
        import prepare
        broken='<remote  name="github"\n           fetch=".."\n           review="review.lineageos.org" />\n<remote name="evo" fetch=".." />'
        fixed,changed=prepare.fix_github_fetch(broken)
        self.assertTrue(changed);self.assertIn('fetch="https://github.com"',fixed);self.assertIn('<remote name="evo" fetch=".." />',fixed)
        self.assertEqual(prepare.fix_github_fetch(fixed),(fixed,False))
    def test_relabel(self):
        import prepare
        new=prepare.relabel(self.METADATA,'evox31','20261105')
        self.assertEqual(new,self.METADATA.replace('evox31','20261105').replace('ab31','ab20261105'))
        second=prepare.relabel(new,'20261105','20261105.2')
        self.assertIn('CONFIG_LOCALVERSION="-android15-8-gf6a5b29f9fe5-ab20261105.2"',second)
        self.assertIn('# 20261105.2: actual',second)
        self.assertEqual(prepare.relabel(second,'20261105.2','20261106').count('ab20261106'),2)
        for text,prev in [(self.METADATA,'evox30'),(self.METADATA.replace('# ab31','# label'),'evox31'),
                          (self.METADATA+'# evox31 again\n','evox31'),(new,'20261105.2'),(second,'20261105'),
                          (self.METADATA.replace('-ab31"','-ab31-x"'),'evox31')]:
            with self.subTest(prev=prev,text=text[:40]),self.assertRaises(ValueError):prepare.relabel(text,prev,'20261107')
    RESOLVED='''<?xml version="1.0" encoding="UTF-8"?>
<manifest>
  <remote name="evo" fetch="https://github.com/Evolution-X" revision="refs/heads/cnb"/>
  <project name="android_device_xiaomi_klimt" path="device/xiaomi/klimt" remote="iowaz" revision="DEV" upstream="cnb" dest-branch="cnb"/>
  <project name="frameworks_native" path="frameworks/native" remote="evo" revision="FINAL" upstream="refs/heads/cnb" dest-branch="refs/heads/cnb" groups="pdk">
    <linkfile src="a" dest="b"/>
  </project>
  <project name="frameworks_av" path="frameworks/av" remote="evo" revision="AV" upstream="refs/heads/cnb" dest-branch="refs/heads/cnb"/>
</manifest>
'''
    def resolved(self,**kw):
        values=dict(DEV='d'*40,FINAL='f'*40,AV='e'*40);values.update(kw)
        text=self.RESOLVED
        for k,v in values.items():text=text.replace('"'+k+'"','"'+v+'"')
        return text
    def test_freeze_pins_patched_projects_at_their_base(self):
        import prepare
        from controller import manifest_heads,effective_heads
        bundle={'frameworks/native':{'base':'a'*40,'final_head':'f'*40}}
        text=prepare.freeze_manifest(self.resolved(),bundle,'20261105')
        heads=manifest_heads(text.encode())
        self.assertEqual(heads,{'device/xiaomi/klimt':'d'*40,'frameworks/native':'a'*40,'frameworks/av':'e'*40})
        self.assertEqual(effective_heads(heads,bundle),manifest_heads(self.resolved().encode()))
        self.assertIn('upstream="refs/heads/cnb" dest-branch="refs/heads/cnb" groups="pdk">',text)
        self.assertEqual(text.count('\n'),self.resolved().count('\n')+2)  # one two-line comment, nothing else changed
        for resolved,b in [(self.resolved(FINAL='9'*40),bundle),(self.resolved(),{'system/core':{'base':'a'*40,'final_head':'f'*40}}),
                           (self.resolved().replace('name="frameworks_av" path="frameworks/av" remote="evo"','name="frameworks_av" path="frameworks/av" remote="iowaz"'),bundle),
                           (self.resolved().replace(' upstream="refs/heads/cnb" dest-branch="refs/heads/cnb" groups','  groups'),bundle)]:
            with self.subTest(b=list(b)),self.assertRaises(ValueError):prepare.freeze_manifest(resolved,b,'20261105')
    def test_renamed_projects_and_comparison_base(self):
        import prepare
        old={'a':{'name':'x'},'b':{'name':'y'},'c':{'name':'z'}}
        new={'a':{'name':'x'},'b':{'name':'y2'},'d':{'name':'w'}}
        self.assertEqual(prepare.renamed_projects(old,new),(['b'],['d'],['c']))
        self.assertEqual(prepare.comparison_base('frameworks/base',{'remote':'iowaz','revision':'r'}),('r','fork'))
        self.assertEqual(prepare.comparison_base('device/xiaomi/klimt',{'remote':'iowaz','revision':'r'}),('r','pin'))
        self.assertEqual(prepare.comparison_base('frameworks/av',{'remote':'evo','revision':'r'}),('r','pin'))
        self.assertEqual(prepare.comparison_base('new/project',None),(None,'added'))
    def test_klimt_manifests_carry_no_forks(self):
        root=B.parents[2]/'manifests/local_manifests'
        for name in ('klimt.xml','klimt-live.xml'):
            with self.subTest(name=name):
                tree=ET_parse((root/name).read_text())
                self.assertEqual(tree.findall('extend-project'),[])
                projects={p.get('path'):p for p in tree.findall('project')}
                self.assertEqual(projects['device/xiaomi/klimt'].get('revision'),'cnb')
                self.assertEqual({p for p,e in projects.items() if e.get('remote')=='iowaz'},{'device/xiaomi/klimt','kernel/xiaomi/klimt','vendor/xiaomi/klimt'})

def ET_parse(text):
    import xml.etree.ElementTree as ET
    return ET.fromstring(text.encode() if isinstance(text,str) else text)

class KernelContract(unittest.TestCase):
    HEAD = '1' * 40
    MAKE = 'VERSION = 6\nPATCHLEVEL = 6\nSUBLEVEL = 144\nEXTRAVERSION =\n'
    COMMON = 'KMI_GENERATION=8\nBRANCH=android15-6.6\n'
    META = '# actual source ' + HEAD + '\nCONFIG_LOCALVERSION="-android15-8-g' + HEAD[:12] + '-ab20261111"\n# CONFIG_LOCALVERSION_AUTO is not set\n'

    def expected(self, **changes):
        import kernel_contract
        args = dict(makefile=self.MAKE, common=self.COMMON, metadata=self.META, head=self.HEAD, build='20261111')
        return kernel_contract.derive(**dict(args, **changes))

    def test_source_release_and_exact_banner(self):
        import kernel_contract
        e = self.expected()
        self.assertEqual(e['release'], '6.6.144-android15-8-g111111111111-ab20261111')
        banner = e['banner_prefix'] + '(test compiler) ' + e['banner_suffix']
        kernel_contract.validate_banner(banner, '20261111', e)
        for old, new in [('6.6.144', '6.6.142'), ('android15-8', 'android15-9'),
                         ('g111111111111', 'g222222222222'), ('ab20261111', 'ab20261112'),
                         ('builder@', 'other@'), ('Aug 6', 'Aug 7')]:
            with self.subTest(new=new), self.assertRaises(ValueError):
                kernel_contract.validate_banner(banner.replace(old, new), '20261111', e)

    def test_source_metadata_and_generation_must_agree(self):
        for args in (dict(head='2'*40), dict(build='20261112'),
                     dict(metadata=self.META.replace('is not set', '=y')),
                     dict(common=self.COMMON.replace('=8', '=9')),
                     dict(common=self.COMMON.replace('android15', 'android16')),
                     dict(makefile=self.MAKE+'SUBLEVEL = 143\n')):
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.expected(**args)

    def test_new_build_cannot_use_historical_fallback(self):
        import kernel_contract
        with self.assertRaises(ValueError):
            kernel_contract.validate_banner('Linux version 6.6.142', '20261111')

    def test_actual_legacy_header_uses_frozen_kernel_expectation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'a/b/pipeline'; legacy=root/'legacy'; legacy.mkdir(parents=True)
            for name in ('kernel_contract.py','paths.py'):
                (root/name).write_bytes((B/name).read_bytes())
            (legacy/'build-profile.sh').write_bytes((B/'legacy/build-profile.sh').read_bytes())
            header=(B/'legacy/fixcheck20.sh').read_text().split('ok(){',1)[0]
            script=legacy/'fixcheck20.sh';script.write_text(header+'\nprintf "%s\\n" "$KERNEL_RELEASE"\n')
            ready=root/'ready.json';ready.write_text(json.dumps({'kernel_expectation':self.expected()}))
            env=dict(os.environ,KLIMT_BUILD='20261111',EVOX_EXTRACT=temp,EVOX_TMP=temp,EVOX_READY=str(ready))
            r=subprocess.run(['bash',str(script)],env=env,text=True,capture_output=True)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual(r.stdout.strip(),self.expected()['release'])
            for changes in ({'KLIMT_BUILD':'20261112'}, {'EVOX_READY':''}):
                r=subprocess.run(['bash',str(script)],env=dict(env,**changes),text=True,capture_output=True)
                self.assertNotEqual(r.returncode,0)

    def test_ready_tooling_cannot_change_or_disappear(self):
        from controller import require_ready_tooling
        ready={'build':'20261111','tooling_sha256':tooling_hashes()}
        require_ready_tooling(ready)
        for changed in ({'build':'20261111'}, dict(ready,tooling_sha256={})):
            with self.assertRaises(RuntimeError):require_ready_tooling(changed)

    def test_source_expectation_is_read_from_commit_not_worktree(self):
        import kernel_contract
        from unittest.mock import patch
        frozen = {kernel_contract.KERNEL: self.HEAD, kernel_contract.DEVICE: '2'*40}
        values = [self.MAKE, self.COMMON, self.META]
        with patch('kernel_contract.subprocess.check_output', side_effect=values) as read:
            e = kernel_contract.source_expectation(frozen, '20261111', '/example')
        self.assertEqual(e['device_head'], '2'*40)
        self.assertEqual(len(e['source_sha256']), 3)
        self.assertTrue(all(call.args[0][-2] == 'show' for call in read.call_args_list))
        self.assertTrue(read.call_args_list[0].args[0][-1].startswith(self.HEAD+':'))

    def test_frozen_candidate_rejects_extra_heads_and_tampered_inputs(self):
        from frozen_candidate import validate_spec
        with tempfile.TemporaryDirectory() as temp:
            spec = dict(schema=1, baseline_sha256='a'*64, tooling_sha256={'x.py': 'b'*64},
                        audit_repository=temp, heads={'kernel/xiaomi/klimt': self.HEAD, 'device/xiaomi/klimt': '2'*40})
            validate_spec(spec, 'a'*64, spec['tooling_sha256'])
            for changed in (dict(spec, baseline_sha256='c'*64), dict(spec, tooling_sha256={}),
                            dict(spec, heads=dict(spec['heads'], **{'frameworks/base': '3'*40})),
                            dict(spec, heads={}), dict(spec, audit_repository='relative')):
                with self.subTest(changed=changed), self.assertRaises(ValueError):
                    validate_spec(changed, 'a'*64, spec['tooling_sha256'])

class CandidateGates(unittest.TestCase):
    def test_abi_graph_requires_all_retained_symbols(self):
        import abi_analysis
        text = 'elf_symbol {\n  name: "one"\n  type_id: 0x1234\n}\nelf_symbol {\n  name: "assembly"\n}\n'
        coverage = abi_analysis.require_coverage(text, {'one', 'assembly'})
        self.assertEqual(coverage, {'symbols': 2, 'untyped': ['assembly']})
        for graph, names in [('', {'one'}), (text, {'one','missing'}), (text, set())]:
            with self.assertRaises(ValueError):
                abi_analysis.require_coverage(graph, names)

    def test_security_equality_blocks_each_changed_security_field(self):
        import rollback_security
        baseline = {'schema': 1, 'actual_source_spl': '2026-11-01', 'avb': {'rollback': 1},
                    'boot_headers': {'boot': {'packed': 17}}, 'reported': {'platform': '2026-10-05'}}
        self.assertTrue(rollback_security.compare(baseline, dict(baseline))['pass'])
        for name in ('actual_source_spl', 'avb', 'boot_headers', 'reported'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                rollback_security.compare(baseline, dict(baseline, **{name: 'changed'}))

    def test_avb_fields_and_chain_locations_are_extracted(self):
        import rollback_security
        text = '''Rollback Index: 1
Rollback Index Location: 0
Flags: 0
Algorithm: SHA256_RSA4096
Public key (sha1): abc
Descriptors:
    Chain Partition descriptor:
      Partition Name: boot
      Rollback Index Location: 3
      Public key (sha1): abc
    Prop: com.android.build.boot.security_patch -> '2026-02-01'
'''
        result = rollback_security.parse_avb(text)
        self.assertEqual(result['chain_partitions'], [['boot', 3, 'abc']])
        self.assertTrue(rollback_security.compare(json.loads(json.dumps(result)), result)['pass'])
        self.assertEqual(result['security_properties'], {'com.android.build.boot.security_patch': '2026-02-01'})
        for changed in (text.replace('Rollback Index: 1\n', ''), text+'Rollback Index: 2\n',
                        text+"    Prop: com.android.build.boot.security_patch -> '2026-03-01'\n"):
            with self.assertRaises(ValueError):
                rollback_security.parse_avb(changed)

    def test_proof_mutation_and_missing_gate_block_audit(self):
        import candidate_gates
        from copy import deepcopy
        from unittest.mock import patch
        def validate(*args):
            with patch('candidate_gates.machine_report_check') as checker:
                result = candidate_gates.validate_audit(*args)
                checker.assert_called_once()
                return result
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)/'proof.txt'; p.write_text('measured proof')
            frozen = {name: 'a'*40 for name in ('kernel/xiaomi/klimt', 'kernel/xiaomi/klimt-prebuilt', 'vendor/xiaomi/klimt')}
            data = dict(schema=1, source_heads=frozen, baseline_manifest_sha256='b'*64, normalized_config_sha256='d'*64,
                        checks={name: dict(pass_=True) for name in ()})
            data['checks'] = {name: {'pass': True, 'explanation': 'reviewed', 'files': [candidate_gates.file_record(p)]}
                              for name in candidate_gates.REQUIRED}
            validate(data, frozen, 'b'*64)
            for name in candidate_gates.REQUIRED:
                changed = deepcopy(data); del changed['checks'][name]
                with self.assertRaises(ValueError):
                    validate(changed, frozen, 'b'*64)
            changed = dict(frozen, **{'kernel/xiaomi/klimt': 'c'*40})
            with self.assertRaises(ValueError):
                validate(data, changed, 'b'*64)
            p.write_text('mutated')
            with self.assertRaises(ValueError):
                validate(data, frozen, 'b'*64)

    def test_freeze_deadline_rejects_expired_and_future_records(self):
        import candidate_gates, datetime
        now = datetime.datetime(2026,11,11,tzinfo=datetime.timezone.utc)
        candidate_gates.freeze_deadline({'control_freeze_utc': '2026-11-05T00:00:00Z'}, now)
        for stamp in ('2026-11-03T00:00:00Z', '2026-11-12T00:00:00Z'):
            with self.assertRaises(ValueError):
                candidate_gates.freeze_deadline({'control_freeze_utc': stamp}, now)

    def test_only_build_label_can_differ_from_analyzed_config(self):
        import candidate_gates
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)/'.config'
            before = 'CONFIG_LOCALVERSION="-old"\nCONFIG_LTO_NONE=y\n# CONFIG_LTO_CLANG is not set\n'
            audit = {'normalized_config_sha256': hashlib.sha256(candidate_gates.normalized_config(before).encode()).hexdigest()}
            p.write_text(before.replace('-old', '-new'))
            candidate_gates.validate_compiled_config(audit, p)
            p.write_text(before+'CONFIG_LTO_CLANG=y\n')
            with self.assertRaises(ValueError):
                candidate_gates.validate_compiled_config(audit, p)

class PostbuildReadinessTests(unittest.TestCase):
    def test_verification_only_ready_cannot_launch_a_build(self):
        from controller import readiness
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'ready.json'
            p.write_text(json.dumps({'build':'20261111','verification_only':True,'tooling_sha256':tooling_hashes()}))
            with self.assertRaisesRegex(RuntimeError,'verifier-only effective readiness cannot launch'):
                readiness(p)

    def test_retained_symbols_are_read_at_the_frozen_kernel_commit(self):
        import kernel_contract
        from unittest.mock import patch
        with patch('kernel_contract.subprocess.check_output',return_value='first_symbol\nsecond_symbol\n') as read:
            symbols=kernel_contract.retained_symbols({'kernel/xiaomi/klimt':'a'*40},'/isolated')
        self.assertEqual(symbols,{'first_symbol','second_symbol'})
        self.assertEqual(read.call_args.args[0][-1],'a'*40+':android/abi_gki_aarch64_klimt')

from test_machine_gates import Reports as MachineReportTests
from test_promotion_tooling import Promotion as PromotionToolingTests
from test_reviewed_readiness import RevalidatedReadiness as RevalidatedReadinessTests
from test_kernel_artifact import Artifact as KernelArtifactTests
from test_kernel_carry import Carry as KernelCarryTests
from test_preserve_kernel_audit import Preserve as PreserveKernelAuditTests
from test_frozen_candidate_flow import CandidateFlow as CandidateFlowTests
from test_vendor_boot_contract import VendorCopies as VendorBootCopyTests
from test_elf_contract import Crcs as ElfCrcTests
from test_release_audit import ReleaseAudit as ReleaseAuditTests

if __name__=='__main__':unittest.main(verbosity=2)
