import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

import candidate_gates
import machine_gates as machine


class Reports(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.audit = {'checks': {}}
        self.frozen = {'kernel/xiaomi/klimt': 'a'*40}
        self.retained = {'one', 'assembly'}
        self.tool = 'd'*64
        self.paths = {}
        self.graph = 'elf_symbol {\n  name: "one"\n  type_id: 0x1234\n}\nelf_symbol {\n  name: "assembly"\n}\n'
        self.add('type_abi', 'old.stg', self.graph)
        self.add('type_abi', 'new.stg', self.graph)
        elf = self.add('type_abi', 'proof.elf', 'bound ELF input')
        source_old = self.add('type_abi', 'old-declaration.h', 'unchanged actual declaration')
        source_new = self.add('type_abi', 'new-declaration.h', 'unchanged actual declaration')
        proof = {'old': str(source_old), 'new': str(source_new), 'sha256': self.sha(source_old)}
        self.add('type_abi', 'assembly-declaration-review.json', {'pass': True, 'source_heads': {'new': 'a'*40},
            'symbols': {'assembly': {'explanation': 'reviewed', 'declarations': [proof], 'providers': [proof]}}})
        inputs = {'symbols': 2, 'untyped': ['assembly'], 'graph_sha256': self.sha(self.paths['old.stg']),
                  'tool_sha256': self.tool, 'inputs': [{'sha256': self.sha(elf)}]}
        self.add('type_abi', 'abi-RESULT.json', {'pass': True, 'exit': 0, 'inputs': {'old': inputs, 'new': inputs}})
        layout = 'struct pkvm_module_ops { int callback; };'
        self.add('pkvm_types', 'pahole-pkvm-baseline.txt', layout)
        self.add('pkvm_types', 'pahole-pkvm-candidate.txt', layout)
        digest = self.sha(self.paths['pahole-pkvm-baseline.txt'])
        self.add('pkvm_types', 'pkvm-compiled-types.json', {'pass': True,
            'byte_identical_pahole_layout_and_signatures': True, 'baseline_sha256': digest, 'candidate_sha256': digest})
        types = ['user_pt_regs', 'kvm_hyp_req', 'kvm_hyp_iommu', 'kvm_hyp_iommu_domain', 'kvm_iommu_paddr_cache',
                 'iommu_iotlb_gather', 'arm_smccc_1_2_regs', 'arm_smccc_res', 'list_head']
        callbacks = '\n'.join('struct '+name+' {};' for name in types)
        self.add('pkvm_types', 'pkvm-callback-types-old.txt', callbacks)
        self.add('pkvm_types', 'pkvm-callback-types-new.txt', callbacks)
        self.add('pkvm_types', 'pkvm-callback-types.json', {'pass': True, 'types': types})
        self.add('module_crc', 'candidate-module-crc.json', {'pass': True, 'mismatches': {}, 'module_layout_mismatches': [],
            'unresolved': ['mtk_drm_gateic_set_backlight'], 'vendor_count': 1, 'module_layout_baseline': 123, 'module_layout_candidate': 123})
        self.add('module_crc', 'vendor-module-contract.json', {'baseline_unresolved': ['mtk_drm_gateic_set_backlight'],
            'vendor_count': 1, 'modules': {'stock.ko': {}}, 'baseline_module_layout': 123})
        self.add('protected_exports', 'protected-policy-report.json', {'pass': True, 'changed': [],
            'source_files': {'policy': {'old': 'same', 'new': 'same'}},
            'intersections': {'newly_restricted_exports': [], 'kernel_imports_outside_whitelist': []},
            'generated_headers': {'header': {'equal': True, 'old_sha256': 'same', 'new_sha256': 'same'}}})
        self.add('symbol_membership', 'symbol-membership.json', {'whitelist': 2, 'tracked_old': 2, 'tracked_target': 2,
            'out_of_contract_old': [], 'out_of_contract_target': [], 'newly_untracked': []})
        self.add('config', 'analysis-status.json', {'state': 'complete', 'exit': 0, 'kernel': 'a'*40})
        config = self.add('config', '.config', 'CONFIG_LOCALVERSION="-trial"\nCONFIG_LTO_NONE=y\n')
        self.audit['normalized_config_sha256'] = hashlib.sha256(candidate_gates.normalized_config(config.read_text()).encode()).hexdigest()
        self.refresh()

    def tearDown(self):
        self.temp.cleanup()

    def sha(self, p):
        return hashlib.sha256(p.read_bytes()).hexdigest()

    def add(self, check, name, value):
        p = self.root/name
        p.write_text(json.dumps(value) if isinstance(value, dict) else value)
        self.paths[name] = p
        self.audit['checks'].setdefault(check, {'pass': True, 'files': []})['files'].append({'path': str(p), 'sha256': self.sha(p)})
        return p

    def refresh(self):
        for check in self.audit['checks'].values():
            for record in check['files']:
                record['sha256'] = self.sha(Path(record['path']))

    def edit(self, name, operation):
        p = self.paths[name]; data = json.loads(p.read_text()); operation(data); p.write_text(json.dumps(data)); self.refresh()

    def validate(self, compare=None):
        # Fresh outer pass flags/hashes cannot mask an inconsistent failed machine result.
        self.assertTrue(all(c['pass'] for c in self.audit['checks'].values()))
        self.assertTrue(all(self.sha(Path(r['path'])) == r['sha256'] for c in self.audit['checks'].values() for r in c['files']))
        return machine.validate(self.audit, self.frozen, self.retained, self.tool, compare or (lambda a,b: 0))

    def test_complete_matching_reports_pass(self):
        self.assertTrue(self.validate()['pass'])

    def test_outer_pass_cannot_hide_failed_abi_exit(self):
        self.edit('abi-RESULT.json', lambda d: d.update(exit=4))
        with self.assertRaises(ValueError): self.validate()

    def test_actual_type_comparison_must_pass(self):
        with self.assertRaises(ValueError): self.validate(lambda a,b: 4)

    def test_incomplete_graph_is_rejected_even_with_fresh_outer_hash(self):
        self.paths['new.stg'].write_text('elf_symbol {\n  name: "one"\n  type_id: 0x1234\n}\n')
        self.refresh()
        with self.assertRaises(ValueError): self.validate()

    def test_crc_failure_cannot_hide_behind_pass_flag(self):
        self.edit('candidate-module-crc.json', lambda d: d.update(mismatches={'bad_symbol': ['stock.ko']}))
        with self.assertRaises(ValueError): self.validate()

    def test_new_unresolved_symbol_is_rejected(self):
        self.edit('candidate-module-crc.json', lambda d: d.update(unresolved=['new_symbol']))
        with self.assertRaises(ValueError): self.validate()

    def test_pkvm_raw_layout_difference_is_rejected(self):
        self.paths['pahole-pkvm-candidate.txt'].write_text('struct pkvm_module_ops { long changed; };')
        self.refresh()
        with self.assertRaises(ValueError): self.validate()

    def test_new_protected_restriction_is_rejected(self):
        self.edit('protected-policy-report.json', lambda d: d['intersections'].update(newly_restricted_exports=['stock_export']))
        with self.assertRaises(ValueError): self.validate()

    def test_out_of_contract_symbol_is_rejected(self):
        self.edit('symbol-membership.json', lambda d: d.update(newly_untracked=['stock_symbol']))
        with self.assertRaises(ValueError): self.validate()

    def test_stale_analysis_head_is_rejected(self):
        self.edit('analysis-status.json', lambda d: d.update(kernel='b'*40))
        with self.assertRaises(ValueError): self.validate()

    def test_changed_assembly_provider_is_rejected(self):
        self.paths['new-declaration.h'].write_text('changed ABI declaration')
        self.refresh()
        with self.assertRaises(ValueError): self.validate()


if __name__ == '__main__': unittest.main(verbosity=2)
