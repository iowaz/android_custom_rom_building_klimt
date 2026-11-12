#!/usr/bin/env python3
"""Simple-mode verification: host guard, resolver, recheck widening, promotion contract and check fixtures.
No Android build, no real image; AVB fixtures use the tree's avbtool when it is present."""
import base64, gzip, hashlib, io, json, os, subprocess, sys, tempfile, unittest, zipfile
os.environ.setdefault('KLIMT_BUILD', 'evox99')
from pathlib import Path

import hostcheck
import verification as v
import simple_checks as sc
from verification import Defect, Missing

B = Path(__file__).resolve().parent
KERNEL = 'kernel/xiaomi/klimt'
AVBTOOL = Path('/mnt/wsl/evox/src/external/avb/avbtool.py')


def ready(**changes):
    heads = {KERNEL: 'kbase', 'kernel/xiaomi/klimt-prebuilt': 'kp', 'vendor/xiaomi/klimt': 'vx', 'hardware/xiaomi': 'hx',
             'vendor/gms': 'g', 'device/xiaomi/klimt': 'd', 'frameworks/base': 'fb'}
    heads.update(changes.pop('heads', {}))
    bundle = {'frameworks/native': dict(**{'class': 'klimt'}, base='nb', final_head='nf', final_tree='nt'),
              'build/make': dict(**{'class': 'personal'}, base='mb', final_head='mf', final_tree='mt')}
    bundle.update(changes.pop('bundle', {}))
    result = dict(build='20261111', target='lineage_klimt-cp2a-user', public_certificate_sha256={'platform': 'p'},
                  reviewed_project_heads=heads, patch_bundle={'projects': bundle})
    result.update(changes)
    return result


IDENTITY = dict(build='20261111', avb_keys={'vbmeta': 'a'*40})


def resolve(current, baseline=None, paths_=(), board='', request=None):
    return v.resolve(current, ready() if baseline is None else baseline, list(paths_) if paths_ is not None else None,
                     board, 'kbase', request or {}, IDENTITY)


class HostGuard(unittest.TestCase):
    def test_windows_python_stops_with_wsl_command(self):
        stream = io.StringIO()
        with self.assertRaises(SystemExit) as stop:
            hostcheck.require_linux('D:\\android_rom_building\\repositories\\x\\verify.py', platform='win32', stream=stream)
        self.assertEqual(stop.exception.code, 2)
        self.assertRegex(stream.getvalue(), r'wsl\.exe -d Ubuntu-24\.04 -- (env KLIMT_BUILD=\S+ )?python3 -B '
                                            r'/mnt/d/android_rom_building/repositories/x/verify\.py')
        self.assertIn('Nothing was created', stream.getvalue())

    def test_linux_passes(self):
        hostcheck.require_linux('verify.py', platform='linux')

    def test_guard_runs_before_linux_only_imports(self):
        for name in ('verify.py', 'promote.py', 'ready.py', 'tool_review.py', 'controller.py', 'prepare.py', 'launch.py'):
            text = (B/name).read_text()
            guard = text.index('hostcheck.require_linux(__file__)')
            for marker in ('import fcntl', 'from controller', 'import controller', 'import kernel_contract', 'import paths'):
                if marker in text:
                    self.assertLess(guard, text.index(marker), (name, marker))


class Resolver(unittest.TestCase):
    def test_unchanged_is_simple(self):
        r = resolve(ready())
        self.assertEqual((r['mode'], r['extras'], r['candidate']), ('simple', [], False))
        self.assertEqual(v.required_checks(r), list(v.SIMPLE_CHECKS))

    def test_candidate_kernel_adds_kernel_and_candidate(self):
        r = resolve(ready(heads={KERNEL: 'knew'}), baseline=ready(heads={KERNEL: 'knew'}))
        self.assertEqual((r['mode'], r['extras'], r['candidate']), ('simple', ['kernel'], True))
        self.assertEqual(v.required_checks(r)[-3:], ['kernel.modules', *v.CANDIDATE_CHECKS])

    def test_full_triggers(self):
        for current in (ready(heads={'vendor/xiaomi/klimt': 'new'}), ready(public_certificate_sha256={'platform': 'q'}),
                        ready(target='lineage_klimt-bp1a-user'),
                        ready(bundle={'external/foo': dict(**{'class': 'klimt'}, base='a', final_head='b', final_tree='c')})):
            self.assertEqual(resolve(current)['mode'], 'full')

    def test_focused_extras(self):
        self.assertEqual(resolve(ready(heads={'hardware/xiaomi': 'n'}))['extras'], ['private_compatibility'])
        self.assertEqual(resolve(ready(heads={'vendor/gms': 'n'}))['extras'], ['gms_themes_apps'])
        self.assertEqual(resolve(ready(heads={'kernel/xiaomi/klimt-prebuilt': 'n'}))['extras'], ['kernel'])
        changed = ready(bundle={'frameworks/native': dict(**{'class': 'klimt'}, base='nb2', final_head='nf2', final_tree='nt2')})
        self.assertEqual(resolve(changed)['extras'], ['patch_packaging'])

    def test_personal_patch_stays_simple(self):
        changed = ready(bundle={'build/make': dict(**{'class': 'personal'}, base='mb2', final_head='mf2', final_tree='mt2')})
        r = resolve(changed)
        self.assertEqual((r['mode'], r['extras']), ('simple', []))
        self.assertTrue(any('identity.metadata' in reason for reason in r['reasons']))

    def test_device_paths(self):
        cases = {('health/health.cpp',): ('simple', ['health_semantics']), ('sepolicy/vendor/x.te',): ('simple', ['policy']),
                 ('overlay/frameworks/base/res/values/config.xml',): ('simple', ['doze_packaging']),
                 ('modules.load.vendor_boot',): ('full', []), ('rootdir/etc/fstab.mt6991',): ('full', []),
                 ('patches/frameworks/native/0001-x.patch',): ('simple', []), ('README.md',): ('simple', []),
                 ('libinit/init_klimt.cpp',): ('simple', [])}
        for names, want in cases.items():
            r = resolve(ready(), paths_=names)
            self.assertEqual((r['mode'], r['extras']), want, names)

    def test_boardconfig_lines(self):
        self.assertEqual(resolve(ready(), paths_=['BoardConfig.mk'], board='+BOARD_SUPER_PARTITION_SIZE := 1\n')['mode'], 'full')
        self.assertEqual(resolve(ready(), paths_=['BoardConfig.mk'], board='-BOARD_AVB_VBMETA_SYSTEM := system\n')['mode'], 'full')
        self.assertEqual(resolve(ready(), paths_=['BoardConfig.mk'], board='+TARGET_SCREEN_DENSITY := 480\n')['mode'], 'simple')

    def test_unknown_inputs_are_full(self):
        self.assertEqual(resolve(ready(), paths_=None)['mode'], 'full')
        self.assertEqual(v.resolve(ready(), None, [], '', 'kbase', {}, None)['mode'], 'full')

    def test_requests_add_never_remove(self):
        with self.assertRaises(ValueError):
            resolve(ready(heads={'vendor/xiaomi/klimt': 'new'}), request=dict(mode='simple'))
        self.assertEqual(resolve(ready(), request=dict(mode='full'))['mode'], 'full')
        self.assertEqual(resolve(ready(heads={'hardware/xiaomi': 'n'}), request=dict(extras=['health_semantics']))['extras'],
                         ['health_semantics', 'private_compatibility'])
        with self.assertRaises(ValueError):
            resolve(ready(), request=dict(extras=['everything']))

    def test_simple_needs_baseline_keys(self):
        with self.assertRaises(ValueError):
            v.resolve(ready(), ready(), [], '', 'kbase', {}, dict(build='20261111'))


class Widening(unittest.TestCase):
    def setUp(self):
        self.simple = resolve(ready())

    def test_add_extras_or_select_full(self):
        self.assertEqual(v.widen(self.simple, dict(self.simple, extras=['policy']))['extras'], ['policy'])
        self.assertEqual(v.widen(self.simple, dict(self.simple, mode='full', extras=[]))['mode'], 'full')
        self.assertIs(v.widen(self.simple, None), self.simple)

    def test_cannot_reduce_or_rebind(self):
        policy = dict(self.simple, extras=['policy'])
        with self.assertRaises(ValueError):
            v.widen(policy, self.simple)
        with self.assertRaises(ValueError):
            v.widen(dict(self.simple, mode='full', extras=[]), self.simple)
        with self.assertRaises(ValueError):
            v.widen(self.simple, dict(self.simple, baseline=dict(IDENTITY, build='20261108')))
        with self.assertRaises(ValueError):
            v.widen(None, self.simple)
        self.assertEqual(v.widen(None, dict(self.simple, mode='full', extras=[]))['mode'], 'full')


class Promotion(unittest.TestCase):
    def setUp(self):
        self.record = resolve(ready())
        self.results = dict(schema=2, verification=self.record, runtime_unvalidated=True,
                            checks=[dict(id=i, outcome='pass') for i in v.SIMPLE_CHECKS])

    def test_exact_passing_list(self):
        self.assertEqual(v.check_results(self.record, self.results), list(v.SIMPLE_CHECKS))

    def test_rejections(self):
        bad = [dict(self.results, checks=self.results['checks'][:-1]),
               dict(self.results, checks=self.results['checks']+[dict(id='staging.clean', outcome='pass')]),
               dict(self.results, checks=[dict(c, outcome='fail') if c['id'] == 'avb.chain' else c for c in self.results['checks']]),
               dict(self.results, verification=dict(self.record, extras=['policy'])),
               dict(self.results, schema=1), dict(self.results, runtime_unvalidated=False)]
        for results in bad:
            with self.assertRaises(ValueError):
                v.check_results(self.record, results)

    def test_full_record_uses_legacy_contract(self):
        with self.assertRaises(ValueError):
            v.check_results(dict(self.record, mode='full', extras=[]), self.results)

    def test_exit_codes(self):
        self.assertEqual([v.exit_code(e) for e in (Defect('x'), Missing('x'), RuntimeError('x'), ValueError('x'), KeyboardInterrupt())],
                         [1, 2, 2, 3, 130])
        self.assertEqual(v.exit_code(subprocess.CalledProcessError(1, ['x'])), 1)
        self.assertEqual(v.exit_code(subprocess.CalledProcessError(9, ['x'])), 3)

    def test_build_order(self):
        names = ['20261105.10', '20261105', 'evox31', '20261105.2', '20261111']
        self.assertEqual(sorted(names, key=v.build_order), ['evox31', '20261105', '20261105.2', '20261105.10', '20261111'])


class Archive(unittest.TestCase):
    def make_zip(self, path, names, compression=zipfile.ZIP_DEFLATED):
        with zipfile.ZipFile(path, 'w', compression) as z:
            for name in names:
                z.writestr(name, (name*50).encode())

    def test_exact_entries_pass_and_hash(self):
        with tempfile.TemporaryDirectory() as d:
            self.make_zip(Path(d)/'a.zip', sorted(sc.ENTRIES))
            members = sc.extract_members(Path(d)/'a.zip', Path(d)/'img')
            self.assertEqual(len(members), 19)
            boot = next(m for m in members if m['name'] == 'boot.img')
            self.assertEqual(boot['sha256'], hashlib.sha256(('boot.img'*50).encode()).hexdigest())

    def test_inventory_defects(self):
        import warnings
        for names in (sorted(sc.ENTRIES)+['extra.img'], sorted(sc.ENTRIES-{'vbmeta.img'}), sorted(sc.ENTRIES)+['boot.img']):
            with tempfile.TemporaryDirectory() as d, warnings.catch_warnings():
                warnings.simplefilter('ignore')
                self.make_zip(Path(d)/'a.zip', names)
                with self.assertRaises(Defect):
                    sc.extract_members(Path(d)/'a.zip', Path(d)/'img')

    def test_crc_defect(self):
        with tempfile.TemporaryDirectory() as d:
            z = Path(d)/'a.zip'
            self.make_zip(z, sorted(sc.ENTRIES), zipfile.ZIP_STORED)
            data = bytearray(z.read_bytes())
            at = data.index(('system.img'*50).encode())
            data[at+5] ^= 0xff
            z.write_bytes(bytes(data))
            with self.assertRaises(Defect):
                sc.extract_members(z, Path(d)/'img')

    def test_copy_digest_must_equal_producer(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d)/'src'
            src.write_bytes(b'abc'*1000)
            good = hashlib.sha256(b'abc'*1000).hexdigest()
            self.assertEqual(sc.copy_with_digest(src, Path(d)/'one.partial', good), good)
            with self.assertRaises(Defect):
                sc.copy_with_digest(src, Path(d)/'two.partial', '0'*64)


LPDUMP_OLD = 'Metadata version: 10.2\n  Name: system_a\n  Group: main_a\n  Attributes: none\n  Name: vendor_a\n  Attributes: none\n'


class Layout(unittest.TestCase):
    def test_readonly_exception_only(self):
        self.assertTrue(sc.readonly_layout_matches(LPDUMP_OLD.replace('none', 'readonly'), LPDUMP_OLD))
        self.assertFalse(sc.readonly_layout_matches(LPDUMP_OLD.replace('none', 'readonly').replace('main_a', 'other'), LPDUMP_OLD))
        self.assertFalse(sc.readonly_layout_matches(LPDUMP_OLD, LPDUMP_OLD))

    def test_reference_files(self):
        with tempfile.TemporaryDirectory() as d:
            ours, ref = Path(d)/'ours', Path(d)/'ref'
            for p in (ours, ref):
                p.mkdir()
                (p/'super_empty.img').write_bytes(b'S')
                (p/'fastboot-info.txt').write_text('flash boot\n')
                (p/'android-info.txt').write_text('require board=klimt\n')
            self.assertEqual(len(sc.flash_layout(ours, {'author': ref}, '/nonexistent/lpdump')), 3)
            (ours/'android-info.txt').write_text('require board=other\n')
            with self.assertRaises(Defect):
                sc.flash_layout(ours, {'author': ref}, '/nonexistent/lpdump')


class Identity(unittest.TestCase):
    def props(self, root, metadata, override=None):
        epoch = '1790000000'
        for part, rel in metadata.PARTS.items():
            values = {f'ro.{part}.build.fingerprint': metadata.FP, f'ro.{part}.build.id': metadata.BID,
                      f'ro.{part}.build.version.incremental': metadata.INC, f'ro.{part}.build.date.utc': epoch,
                      f'ro.{part}.build.type': 'user', f'ro.{part}.build.tags': 'release-keys',
                      f'ro.product.{part}.brand': 'Xiaomi', f'ro.product.{part}.device': 'klimt',
                      f'ro.product.{part}.manufacturer': 'Xiaomi', f'ro.product.{part}.model': '2506BPN68G'}
            if part in ('system', 'product'):
                values.update({'ro.build.fingerprint': metadata.FP, 'ro.build.id': metadata.BID, 'ro.build.display.id': metadata.BID,
                               'ro.build.version.incremental': metadata.INC, 'ro.build.flavor': 'klimt_global-user',
                               'ro.build.description': f'klimt_global-user 17 {metadata.BID} {metadata.INC} release-keys',
                               'ro.build.user': 'builder', 'ro.build.host': metadata.HOST, 'ro.build.date.utc': epoch,
                               'ro.build.version.known_codenames': metadata.KNOWN, 'ro.build.version.security_patch': '2026-10-05',
                               'ro.build.version.codename': 'REL', 'ro.build.version.all_codenames': 'REL',
                               'ro.build.version.release': '17'})
            if part == 'system':
                values['ro.bootimage.fingerprint'] = metadata.FP
            if part == 'vendor':
                values['ro.vendor.build.security_patch'] = '2026-10-05'
            values.update((override or {}).get(part, {}))
            (Path(root)/rel).parent.mkdir(parents=True, exist_ok=True)
            (Path(root)/rel).write_text(''.join(f'{k}={x}\n' for k, x in values.items()))

    def test_identity_props_and_banner(self):
        metadata = sc.load_script('check_metadata26', B/'check-metadata26.py')
        expectation = dict(build='20261112', banner_prefix='Linux version 6.6.142', banner_suffix='-ab20261112')
        banner = 'Linux version 6.6.142-android15-8-gabc-ab20261112'
        with tempfile.TemporaryDirectory() as d:
            self.props(d, metadata)
            self.assertEqual(sc.identity_metadata(d, banner, '20261112', expectation)['assertions'], 112)
            with self.assertRaises(Defect):
                sc.identity_metadata(d, banner.replace('ab20261112', 'ab20261111'), '20261112', expectation)
        with tempfile.TemporaryDirectory() as d:
            self.props(d, metadata, {'vendor': {'ro.vendor.build.fingerprint': 'google/bluejay/bluejay:16/x/y:user/release-keys'}})
            with self.assertRaises(Defect):
                sc.identity_metadata(d, banner, '20261112', expectation)
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(Missing):
                sc.identity_metadata(d, banner, '20261112', expectation)

    def test_kernel_banner(self):
        kernel = b'\x00junk Linux version 6.6.142-x (builder@host) #1 SMP\n\x00more'
        self.assertEqual(sc.kernel_banner(kernel), 'Linux version 6.6.142-x (builder@host) #1 SMP')
        self.assertEqual(sc.kernel_banner(sc.decompress(gzip.compress(kernel))), 'Linux version 6.6.142-x (builder@host) #1 SMP')
        self.assertIsNone(sc.kernel_banner(b'no banner'))


class Staging(unittest.TestCase):
    TELECOM = 'system/priv-app/TelecomShim/TelecomShim.apk'
    LEGACY = 'system/priv-app/Telecom/Telecom.apk'

    def evidence(self, d, staged_extra=(), installable_extra=(), **facts):
        installed = ['system/framework/framework.jar', self.TELECOM, *installable_extra]
        kernel = [f'vendor_dlkm/lib/modules/m{i}.ko' for i in range(650)]
        (Path(d)/'installable_files.txt').write_text(' '.join('out/target/product/klimt/'+p for p in installed))
        (Path(d)/'staged-paths.txt').write_text('\n'.join([*installed, *kernel, *staged_extra])+'\n')
        base = dict(listing='.installable_files', listing_mtime_ns=20, started_ns=10, telecom_mainline='true',
                    selected_telecom=['TelecomShim'])
        base.update(facts)
        (Path(d)/'facts.json').write_text(json.dumps(base))
        return d

    def test_clean_staging_passes(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(sc.staging_clean(self.evidence(d))['telecom'], self.TELECOM)

    def test_evox16_stray_telecom_fails(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(Defect):
                sc.staging_clean(self.evidence(d, staged_extra=[self.LEGACY]))
        with tempfile.TemporaryDirectory() as d:  # even when the product had listed it
            with self.assertRaises(Defect):
                sc.staging_clean(self.evidence(d, staged_extra=[self.LEGACY], installable_extra=[self.LEGACY]))

    def test_other_defects(self):
        for facts in (dict(listing_mtime_ns=5), dict(selected_telecom=['Telecom']), dict(telecom_mainline='false')):
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(Defect):
                    sc.staging_clean(self.evidence(d, **facts))
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(Missing):
                sc.staging_clean(self.evidence(d, telecom_mainline=None))

    def test_capture_at_packaging(self):
        import staging_evidence
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            product, attempt, src = root/'product', root/'attempt', root/'src'
            for rel in staging_evidence.STAGED_PROPS.values():
                (product/rel).parent.mkdir(parents=True, exist_ok=True)
                (product/rel).write_text('ro.x=1\n')
            (product/'system/priv-app/TelecomShim').mkdir(parents=True)
            (product/'system/priv-app/TelecomShim/TelecomShim.apk').write_bytes(b'apk')
            (product/'system/framework/framework-res.apk').parent.mkdir(parents=True, exist_ok=True)
            (product/'system/framework/framework-res.apk').write_bytes(b'apk')
            (product/'.installable_files.previous').write_text('out/target/product/klimt/system/build.prop\n')
            attempt.mkdir()
            (attempt/'owner.json').write_text(json.dumps(dict(started_ns=1)))
            variables = root/'soong.variables'
            # The 20261111 layout: the selection sits outside VendorVars.
            variables.write_text(json.dumps({'CertificateOverrides': ['TelecomUi:com.android.telecomui.certificate.override'],
                                             'VendorVars': {'ANDROID': {'release_telecom_mainline_module': 'true'}},
                                             'PartitionVarsForSoongMigrationOnlyDoNotUse': {'ProductPackagesSet': {'all': {
                                                 'ProductPackages': ['Settings', 'TelecomShim']}}}}))
            tool = src/'out/host/linux-x86/bin/apksigner'
            tool.parent.mkdir(parents=True)
            tool.write_text('#!/bin/sh\necho "Signer #1 certificate SHA-256 digest: ' + 'ab'*32 + '"\n')
            tool.chmod(0o755)
            digests = staging_evidence.capture(attempt, product, variables, src)
            self.assertIn('props/system/system/build.prop', digests)
            self.assertIn('system/priv-app/TelecomShim/TelecomShim.apk', (attempt/'staging-evidence/staged-paths.txt').read_text())
            facts = json.loads((attempt/'staging-evidence/facts.json').read_text())
            self.assertEqual((facts['listing'], facts['telecom_mainline'], facts['selected_telecom'], facts['apksigner_exit']),
                             ('.installable_files.previous', 'true', ['TelecomShim'], 0))


class Signing(unittest.TestCase):
    PEM = '-----BEGIN CERTIFICATE-----\n' + base64.b64encode(b'certificate-bytes').decode() + '\n-----END CERTIFICATE-----\n'
    DIGEST = hashlib.sha256(b'certificate-bytes').hexdigest()

    def test_single_platform_signer(self):
        self.assertEqual(sc.platform_signer(f'Signer #1 certificate SHA-256 digest: {self.DIGEST}\n', 0, self.PEM)
                         ['platform_certificate_sha256'], self.DIGEST)
        # 20261111's framework-res.apk is v3-only; apksigner prints it this way.
        v3 = (f'V3.0 Signer: certificate DN: CN=Android\nV3.0 Signer: certificate SHA-256 digest: {self.DIGEST}\n'
              f'V3.0 Signer: certificate SHA-1 digest: {"2"*40}\n')
        self.assertEqual(sc.platform_signer(v3, 0, self.PEM)['platform_certificate_sha256'], self.DIGEST)
        with self.assertRaises(Defect):
            sc.platform_signer('V3.0 Signer: certificate DN: CN=Android\n', 0, self.PEM)
        for text, code in ((f'Signer #1 certificate SHA-256 digest: {"0"*64}\n', 0),
                           (f'Signer #1 certificate SHA-256 digest: {self.DIGEST}\nSigner #2 certificate SHA-256 digest: {"1"*64}\n', 0),
                           (f'Signer #1 certificate SHA-256 digest: {self.DIGEST}\n', 1)):
            with self.assertRaises(Defect):
                sc.platform_signer(text, code, self.PEM)


class Evidence(unittest.TestCase):
    def test_build_exit_binds_staging_evidence(self):
        from verify import staging_evidence
        with tempfile.TemporaryDirectory() as d:
            attempt = Path(d)
            (attempt/'staging-evidence').mkdir()
            (attempt/'staging-evidence/facts.json').write_text('{}')
            good = {'facts.json': hashlib.sha256(b'{}').hexdigest()}
            self.assertEqual(staging_evidence(attempt, {'staging_evidence': good}), attempt/'staging-evidence')
            with self.assertRaises(Missing):
                staging_evidence(attempt, {'staging_evidence_error': 'apksigner unavailable'})
            with self.assertRaises(Defect):
                staging_evidence(attempt, {'staging_evidence': {'facts.json': '0'*64}})
            with self.assertRaises(Defect):
                staging_evidence(attempt, {'staging_evidence': dict(good, **{'missing.txt': '0'*64})})

    def test_kernel_modules_need_symvers(self):
        with self.assertRaises(Missing):
            sc.kernel_modules('/nonexistent/Module.symvers', [])


@unittest.skipUnless(AVBTOOL.is_file(), 'avbtool from the tree')
class Avb(unittest.TestCase):
    def avb(self, *args):
        subprocess.run(['python3', str(AVBTOOL), *map(str, args)], check=True, capture_output=True)

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        d = self.root = Path(self.dir.name)
        for name in ('k1', 'k2'):
            subprocess.run(['openssl', 'genrsa', '-out', str(d/f'{name}.pem'), '2048'], check=True, capture_output=True)
        self.avb('extract_public_key', '--key', d/'k2.pem', '--output', d/'k2.bin')
        (d/'boot.img').write_bytes(os.urandom(65536))
        (d/'system.img').write_bytes(os.urandom(65536))
        self.avb('add_hash_footer', '--image', d/'boot.img', '--partition_name', 'boot', '--partition_size', 262144)
        self.avb('add_hash_footer', '--image', d/'system.img', '--partition_name', 'system', '--partition_size', 262144)
        self.avb('make_vbmeta_image', '--output', d/'vbmeta_system.img', '--algorithm', 'SHA256_RSA2048', '--key', d/'k2.pem',
                 '--include_descriptors_from_image', d/'system.img')
        self.avb('make_vbmeta_image', '--output', d/'vbmeta.img', '--algorithm', 'SHA256_RSA2048', '--key', d/'k1.pem',
                 '--include_descriptors_from_image', d/'boot.img', '--chain_partition', f'vbmeta_system:1:{d/"k2.bin"}')
        info = subprocess.run(['python3', str(AVBTOOL), 'info_image', '--image', str(d/'vbmeta.img')], check=True,
                              capture_output=True, text=True).stdout
        self.keys = v.vbmeta_keys(info)

    def tearDown(self):
        self.dir.cleanup()

    def test_chain_verifies_with_baseline_keys(self):
        self.assertEqual(set(self.keys), {'vbmeta', 'vbmeta_system'})
        self.assertEqual(sc.avb_chain(self.root, AVBTOOL, self.keys)['public_keys_sha1'], self.keys)

    def test_tampered_chained_image_fails(self):
        data = bytearray((self.root/'system.img').read_bytes())
        data[100] ^= 0xff
        (self.root/'system.img').write_bytes(bytes(data))
        with self.assertRaises(Defect):
            sc.avb_chain(self.root, AVBTOOL, self.keys)

    def test_changed_key_fails(self):
        with self.assertRaises(Defect):
            sc.avb_chain(self.root, AVBTOOL, dict(self.keys, vbmeta='0'*40))

    def test_dtbo_payload_reads_descriptor_size(self):
        self.assertEqual(sc.avb_payload_sha(self.root/'boot.img', AVBTOOL),
                         hashlib.sha256((self.root/'boot.img').read_bytes()[:65536]).hexdigest())


if __name__ == '__main__':
    unittest.main()
