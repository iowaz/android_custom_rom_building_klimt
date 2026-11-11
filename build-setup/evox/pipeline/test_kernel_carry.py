import copy
import json
from pathlib import Path
import tempfile
import unittest

import kernel_carry as gate


class Carry(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.manifest=Path(self.temp.name)/'control.xml';self.manifest.write_text('control manifest')
        self.heads={p:'a'*40 for p in gate.CONTRACT};self.heads['device/xiaomi/klimt']='b'*40
        self.parent={'source_heads':{p:self.heads[p] for p in gate.CONTRACT},
                     'normalized_config_sha256':'c'*64,'baseline_manifest_sha256':'d'*64}
        self.chain=dict(audit=dict(path='old.json',sha256='1'*64),control_results=dict(path='results.json',sha256='2'*64),
                        control_manifest=dict(path=str(self.manifest),sha256='3'*64),
                        control_archive=dict(path='control.zip',sha256='4'*64))
        self.audit=copy.deepcopy(self.parent);self.audit.update(baseline_manifest_sha256='3'*64,kernel_carry=self.chain)
        coverage=['policy','patch_packaging','private_compatibility','health_semantics','gms_themes_apps','doze_packaging','install_integrity']
        self.results=dict(source_heads=copy.deepcopy(self.heads),candidate_evidence={'kernel_audit':self.chain['audit']},
                          archive_sha256='4'*64,historical={'musthold':'pass','checks':[{'pass':True}]},
                          supplemental=[dict(coverage=c,exit=0) for c in coverage])
        self.calls=[]

    def validate(self, parent_check=None, actual=None):
        data={'old.json':self.parent,'results.json':self.results}
        hashes={str(self.manifest):'3'*64,'control.zip':'4'*64}
        return gate.validate(self.audit,self.heads,lambda r:data[r['path']],
                             parent_check or (lambda p:self.calls.append(p)),lambda raw:copy.deepcopy(self.heads),
                             actual or (lambda p:hashes[p]))

    def test_unchanged_contract_requires_verified_parent(self):
        self.validate();self.assertEqual(self.calls,[self.parent])
        self.assertEqual(self.audit['baseline_manifest_sha256'],'3'*64)
        self.assertEqual(self.parent['baseline_manifest_sha256'],'d'*64)

    def test_changed_kernel_prebuilt_vendor_or_config_cannot_be_carried(self):
        for p in gate.CONTRACT:
            with self.subTest(project=p):
                old=self.parent['source_heads'][p];self.parent['source_heads'][p]='9'*40
                with self.assertRaises(ValueError):self.validate()
                self.parent['source_heads'][p]=old
        self.audit['normalized_config_sha256']='9'*64
        with self.assertRaises(ValueError):self.validate()

    def test_changed_control_or_wrong_parent_is_rejected(self):
        with self.assertRaises(ValueError):self.validate(actual=lambda p:'9'*64)
        self.results['candidate_evidence']['kernel_audit']=dict(path='other.json',sha256='9'*64)
        with self.assertRaises(ValueError):self.validate()

    def test_failed_control_or_parent_is_not_reusable(self):
        self.results['supplemental'][0]['exit']=1
        with self.assertRaises(ValueError):self.validate()
        self.results['supplemental'][0]['exit']=0
        def failed(parent):raise ValueError('Parent ABI proof failed')
        with self.assertRaises(ValueError):self.validate(parent_check=failed)
