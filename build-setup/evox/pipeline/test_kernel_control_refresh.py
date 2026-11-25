import copy
import datetime
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import kernel_control_refresh as gate
import kernel_carry


class RefreshControl(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.manifest = Path(self.temp.name) / 'control.xml'; self.manifest.write_text('manifest')
        self.heads = {p:'a'*40 for p in gate.kernel_carry.CONTRACT}
        self.heads['device/xiaomi/klimt'] = 'b'*40
        expected = json.loads((gate.paths.PIPELINE/'expected-legacy-checks.json').read_text())
        def ref(p, sha='f'*64):return dict(path=str(p),sha256=sha)
        self.record = dict(schema=1,mode=gate.MODE,build='20261119',control_build='20261118',
            snapshot_sha256='new',control_manifest=ref(self.manifest,'control'),tooling_sha256={'t':'x'},
            validated_utc='2026-11-19T18:00:00Z',control_archive=ref('/delivery/control.zip','archive'),
            control_results=ref('/report/RESULTS.json'),build_exit=ref('exit'),promotion=ref('promotion'),
            control_ready=ref('ready'),fresh_binding=ref('binding'),fresh_security=ref('fresh'),
            verified_security=ref('/report/rollback-security-candidate.json','security'),certificates={'platform':'cert'},
            reports={n:ref('/report/'+n) for n in gate.REPORTS})
        results=dict(source_heads=copy.deepcopy(self.heads),archive_sha256='archive',archive_bytes=123,
            historical=dict(musthold='pass',checks=[dict(name=n,pass_=True) for n in expected]),
            supplemental=[dict(coverage=n,exit=0) for n in gate.COVERAGE],
            candidate_evidence={'kernel_audit':ref('audit')},kernel_artifact_evidence={n:'f'*64 for n in gate.REPORTS},
            rollback_security={'rollback-security-candidate.json':'security'})
        for c in results['historical']['checks']:c['pass']=c.pop('pass_')
        self.values={'/report/RESULTS.json':results,'exit':dict(exit=0,zip_sha256='archive',zip_bytes=123),
            'promotion':dict(build='20261118',archive_sha256='archive',report='/report',delivery='/delivery'),
            'audit':{'baseline_manifest_sha256':'older'},'binding':{'pass':True},
            'fresh':dict(baseline_manifest_sha256='control',verified_results=self.record['control_results'],
                         archive=self.record['control_archive'],security={'spl':'2026-11-01'}),
            '/report/rollback-security-candidate.json':{'spl':'2026-11-01'},
            'ready':dict(public_certificate_sha256={'platform':'cert'},effective_project_heads=copy.deepcopy(self.heads)),
            '/report/kernel-artifact-binding.json':{'pass':True},'/report/image-files.json':[],
            '/report/filesystem-files.json':[]}
        self.hashes={str(self.manifest):'control','/delivery/control.zip':'archive'}
        self.now=datetime.datetime(2026,11,19,19,tzinfo=datetime.timezone.utc)

    def validate(self):
        def load(r):
            if r['sha256'] not in ('f'*64,'security'):raise ValueError('hash drift')
            return self.values[r['path']]
        return gate.validate(self.record,'20261119','new','control',self.heads,{'t':'x'},load=load,
            heads=lambda raw:self.heads,now=self.now,proof_check=lambda *a:None,binding_check=lambda *a:None,
            digest=lambda p:self.hashes.get(str(p),'cert'))

    def test_fresh_passing_delivered_control(self):
        self.validate()

    def test_build_snapshot_baseline_and_tooling_cannot_transfer(self):
        for key,value in [('build','20261120'),('snapshot_sha256','other'),('tooling_sha256',{})]:
            with self.subTest(key=key):
                old=self.record[key];self.record[key]=value
                with self.assertRaises(ValueError):self.validate()
                self.record[key]=old

    def test_expired_and_future_receipts_fail(self):
        for stamp in ('2026-11-01T18:00:00Z','2026-11-20T18:00:00Z'):
            self.record['validated_utc']=stamp
            with self.assertRaises(ValueError):self.validate()

    def test_incomplete_or_failed_full_verification_fails(self):
        result=self.values['/report/RESULTS.json']; original=copy.deepcopy(result)
        for mutate in (lambda:result['historical']['checks'].pop(),
                       lambda:result['historical']['checks'][0].update({'pass':False}),
                       lambda:result['supplemental'].pop(),
                       lambda:result['supplemental'][0].update(exit=1)):
            mutate()
            with self.assertRaises(ValueError):self.validate()
            result.clear();result.update(copy.deepcopy(original))

    def test_archive_manifest_proof_and_inventory_drift_fail(self):
        for name in list(self.hashes):
            old=self.hashes[name];self.hashes[name]='changed'
            with self.assertRaises(ValueError):self.validate()
            self.hashes[name]=old
        self.record['reports']['image-files.json']['sha256']='changed'
        with self.assertRaises(ValueError):self.validate()

    def test_security_binding_certificate_and_producing_artifact_failures(self):
        cases=[('binding','pass',False),('fresh','security',{'spl':'wrong'}),
               ('ready','public_certificate_sha256',{}),('exit','exit',1),('promotion','delivery','/other')]
        for name,key,value in cases:
            old=self.values[name][key];self.values[name][key]=value
            with self.assertRaises(ValueError):self.validate()
            self.values[name][key]=old

    def test_carry_does_not_transfer_verifier_only_admission(self):
        parent={'baseline_manifest_sha256':'old','control_revalidation':{'path':'old-only','sha256':'old'}}
        with patch.object(kernel_carry.candidate_gates,'revalidate',side_effect=[parent,{}]), \
             patch.object(kernel_carry.candidate_gates,'validate_audit'):
            result=kernel_carry.carry({'path':'parent'}, {}, {'path':str(self.manifest),'sha256':'control'},
                {'path':'archive'},self.heads,lambda raw:self.heads)
        self.assertNotIn('control_revalidation',result)
        self.assertIn('control_revalidation',parent)
        self.assertEqual(result['kernel_carry']['audit'],{'path':'parent'})
