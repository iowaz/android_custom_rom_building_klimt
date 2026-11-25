import copy
import datetime
import unittest

import control_revalidation as gate
import candidate_gates


class ControlRevalidation(unittest.TestCase):
    def setUp(self):
        self.now = datetime.datetime(2026, 11, 18, 16, tzinfo=datetime.timezone.utc)
        self.prep = dict(baseline_sha256='baseline', control_freeze_utc='2026-11-11T15:04:25Z')
        self.chain = dict(control_results={'path': '/control/RESULTS.json', 'sha256': 'r'},
                          control_archive={'path': '/control.zip', 'sha256': 'archive'})
        self.audit = dict(kernel_carry=self.chain, normalized_config_sha256='config', source_heads={'kernel': 'pin'})
        self.ready = dict(build='20261118', verification_only=True, verification_attempt='20261118-attempt01',
            candidate_evidence={'preparation': {'path': 'prep', 'sha256': 'p'},
                                'rollback_baseline': {'path': 'baseline', 'sha256': 'b'}},
            sha256='snapshot', reviewed_project_heads={'kernel': 'pin'}, tooling_sha256={'old': 'tool'},
            public_certificate_sha256={'platform': 'cert'}, security={'platform_security_patch': '2026-11-01'})
        security = {'actual_source_spl': '2026-11-01', 'avb': {'key': 'trusted'}}
        binding = {'pass': True, 'image': 'exact'}
        self.data = {
            'exit': {'exit': 0, 'zip_sha256': 'zip', 'zip_bytes': 100},
            '/control/RESULTS.json': {'source_heads': {'kernel': 'pin'},
                'kernel_artifact_evidence': {'kernel-artifact-binding.json': 'binding'}},
            'fresh': {'baseline_manifest_sha256': 'baseline', 'verified_results': self.chain['control_results'],
                      'archive': {'sha256': 'archive'}, 'security': security},
            'baseline': {'security': copy.deepcopy(security)}, 'binding': binding,
            '/control/kernel-artifact-binding.json': copy.deepcopy(binding),
            'review': {'pass': True, 'source_spl': '2026-11-01', 'certificates': {'platform': 'cert'},
                       'bulletin': {'state': 'merged'}},
            'control-ready': {'effective_project_heads': {'kernel': 'pin'},
                              'public_certificate_sha256': {'platform': 'cert'}}}
        self.record = dict(schema=1, mode=gate.MODE, build='20261118', attempt='20261118-attempt01',
            preparation=self.ready['candidate_evidence']['preparation'], snapshot_sha256='snapshot',
            heads_sha256=gate.canonical(self.ready['reviewed_project_heads']),
            admission_tooling={'old': 'tool'}, tooling_sha256={'current': 'tool'},
            audit_sha256=gate.audit_identity(self.audit), baseline_sha256='baseline',
            original_freeze_utc=self.prep['control_freeze_utc'], certificates={'platform': 'cert'},
            verified_control=self.chain, build_exit={'path': '/20261118-attempt01/build-exit.json', 'sha256': 'e'},
            archive_sha256='zip', archive_bytes=100, fresh_security={'path': 'fresh'},
            fresh_kernel_binding={'path': 'binding'}, security_review={'path': 'review'},
            control_ready={'path': 'control-ready'}, validated_utc='2026-11-18T15:30:00Z')

    def validate(self):
        def load(record):
            return self.data['exit' if record['path'].endswith('/build-exit.json') else record['path']]
        return gate.validate(self.record, self.ready, self.prep, self.audit, load, self.now, {'current': 'tool'})

    def test_fresh_separate_control_admits_only_this_verification(self):
        before = copy.deepcopy((self.prep, self.ready, self.audit))
        self.validate()
        self.assertEqual((self.prep, self.ready, self.audit), before)
        with self.assertRaises(ValueError):
            candidate_gates.freeze_deadline(self.prep, self.now)

    def test_cannot_launch_or_transfer_to_another_attempt(self):
        self.ready['verification_only'] = False
        with self.assertRaises(ValueError): self.validate()
        self.ready['verification_only'] = True
        self.ready['verification_attempt'] = '20261118-attempt02'
        with self.assertRaises(ValueError): self.validate()

    def test_expired_future_or_backdated_revalidation_fails(self):
        for stamp in ('2026-11-10T15:00:00Z', '2026-11-19T15:00:00Z', '2026-11-11T15:04:25Z'):
            with self.subTest(stamp=stamp):
                self.record['validated_utc'] = stamp
                with self.assertRaises(ValueError): self.validate()

    def test_source_preparation_tooling_audit_and_keys_are_bound(self):
        for field in ('snapshot_sha256', 'heads_sha256', 'preparation', 'admission_tooling', 'tooling_sha256',
                      'audit_sha256', 'baseline_sha256', 'original_freeze_utc', 'certificates', 'verified_control'):
            with self.subTest(field=field):
                old = self.record[field]; self.record[field] = 'changed'
                with self.assertRaises(ValueError): self.validate()
                self.record[field] = old

    def test_failed_or_changed_archive_cannot_be_revalidated(self):
        for field, value in [('exit', 1), ('zip_sha256', 'changed'), ('zip_bytes', 200)]:
            old = self.data['exit'][field]; self.data['exit'][field] = value
            with self.assertRaises(ValueError): self.validate()
            self.data['exit'][field] = old

    def test_security_binding_control_keys_and_bulletin_must_pass(self):
        for path, field, value in [('fresh', 'security', {}), ('binding', 'pass', False),
                ('review', 'source_spl', '2026-10-01'), ('review', 'bulletin', {'state': 'unavailable'}),
                ('control-ready', 'public_certificate_sha256', {'platform': 'wrong'}),
                ('control-ready', 'effective_project_heads', {'kernel': 'wrong'})]:
            with self.subTest(path=path, field=field):
                old = self.data[path][field]; self.data[path][field] = value
                with self.assertRaises(ValueError): self.validate()
                self.data[path][field] = old

    def test_receipt_hash_drift_is_not_suppressed(self):
        def drift(record): raise ValueError('evidence hash drift')
        with self.assertRaisesRegex(ValueError, 'hash drift'):
            gate.validate(self.record, self.ready, self.prep, self.audit, drift, self.now, {'current': 'tool'})


if __name__ == '__main__': unittest.main(verbosity=2)
