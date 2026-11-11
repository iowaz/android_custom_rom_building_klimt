import copy
import unittest
import reviewed_readiness as gate


class RevalidatedReadiness(unittest.TestCase):
    def setUp(self):
        self.ready = {'reviewed_project_heads': {'kernel/xiaomi/klimt': 'a'*40},
                      'candidate_evidence': {'preparation': 'unchanged', 'rollback_baseline': 'unchanged',
                                             'kernel_audit': {'path': 'old.json', 'sha256': '1'*64}}}
        self.review = {'kernel_audit_previous_sha256': '1'*64, 'kernel_audit_update': {'path':'new.json','sha256':'2'*64}}
        old = {'source_heads': {'kernel/xiaomi/klimt':'a'*40}, 'baseline_manifest_sha256':'b'*64}
        self.data = {'old.json':old, 'new.json':copy.deepcopy(old)}
        self.calls = []

    def run_gate(self, validator=None):
        return gate.apply(self.ready,self.review,lambda r:self.data[r['path']],validator or (lambda r,h:self.calls.append((r,h))))

    def test_revalidated_same_source_audit_updates_only_verification(self):
        before=copy.deepcopy(self.ready)
        result=self.run_gate()
        self.assertEqual(self.ready,before)
        self.assertEqual(result['candidate_evidence']['kernel_audit'],self.review['kernel_audit_update'])
        self.assertEqual(result['candidate_evidence']['preparation'],'unchanged')
        self.assertEqual(result['candidate_evidence']['rollback_baseline'],'unchanged')
        self.assertTrue(result['verification_only']);self.assertEqual(len(self.calls),1)

    def test_changed_source_or_control_is_rejected(self):
        for key in ('source_heads','baseline_manifest_sha256'):
            with self.subTest(key=key):
                saved=copy.deepcopy(self.data['new.json']);self.data['new.json'][key]='changed'
                with self.assertRaises(ValueError):self.run_gate()
                self.data['new.json']=saved

    def test_bad_original_binding_is_rejected(self):
        self.review['kernel_audit_previous_sha256']='wrong'
        with self.assertRaises(ValueError):self.run_gate()

    def test_failed_replacement_gate_is_rejected(self):
        def failing(r,h):raise ValueError('replacement type/config/CRC proof failed')
        with self.assertRaises(ValueError):self.run_gate(failing)

    def test_cannot_add_candidate_admission_to_ordinary_build(self):
        del self.ready['candidate_evidence']
        with self.assertRaises(ValueError):self.run_gate()


if __name__ == '__main__':unittest.main(verbosity=2)
