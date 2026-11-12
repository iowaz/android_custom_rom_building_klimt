import copy
import tempfile
from pathlib import Path
import unittest

import upstream_kernel_control as gate


class UpstreamControl(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.manifest = Path(self.temp.name) / 'control.xml'; self.manifest.write_bytes(b'control')
        self.frozen = {p: 'a'*40 for p in gate.kernel_carry.CONTRACT}
        self.frozen.update({'device/xiaomi/klimt': 'b'*40, 'frameworks/base': 'c'*40})
        self.control = dict(self.frozen, **{'frameworks/base': 'd'*40})
        self.tooling = {'tool.py': 'e'*64}
        self.record = dict(schema=1, mode=gate.MODE, build='20261112.2', baseline=str(self.manifest),
            baseline_sha256='f'*64, frozen_sha256='1'*64, tooling_sha256=self.tooling,
            heads={p:self.frozen[p] for p in (gate.kernel_contract.KERNEL, gate.kernel_contract.DEVICE)},
            source_preparation={name:{'path':name,'sha256':'2'*64} for name in gate.STEPS})
        self.proofs = {name:dict(ok=True, step=step, build='20261112.2') for name,step in gate.STEPS.items()}
        self.proofs['SYNC.json']['exit'] = 0
        self.proofs['PATCH.json'].update(check_exit=0, check_output=['FINAL frameworks/base'])
        self.proofs['FREEZE.json'].update(sha256='1'*64, device_head=self.frozen[gate.kernel_contract.DEVICE])

    def validate(self):
        return gate.validate(self.record, self.frozen, '1'*64, self.tooling,
                             load=lambda r:self.proofs[r['path']], heads=lambda raw:self.control, digest=lambda p:'f'*64)

    def test_complete_refreshed_rom_keeps_verified_kernel(self):
        self.validate()

    def test_incomplete_failed_or_foreign_preparation_is_rejected(self):
        for name in gate.STEPS:
            with self.subTest(name=name):
                original = copy.deepcopy(self.proofs[name])
                for key,value in [('ok',False),('build','20261111')]:
                    self.proofs[name][key]=value
                    with self.assertRaises(ValueError):self.validate()
                    self.proofs[name]=copy.deepcopy(original)
        del self.record['source_preparation']['SYNC.json']
        with self.assertRaises(ValueError):self.validate()

    def test_snapshot_tooling_and_kernel_drift_are_rejected(self):
        for key,value in [('frozen_sha256','9'*64),('tooling_sha256',{})]:
            old=self.record[key];self.record[key]=value
            with self.assertRaises(ValueError):self.validate()
            self.record[key]=old
        self.control[gate.kernel_contract.KERNEL]='9'*40
        with self.assertRaises(ValueError):self.validate()

    def test_unapplied_patch_or_wrong_frozen_device_is_rejected(self):
        self.proofs['PATCH.json']['check_output']=['BASE frameworks/base']
        with self.assertRaises(ValueError):self.validate()
        self.proofs['PATCH.json']['check_output']=['FINAL frameworks/base']
        self.proofs['FREEZE.json']['device_head']='9'*40
        with self.assertRaises(ValueError):self.validate()
