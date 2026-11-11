import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import candidate_gates
import release_audit as gate


class ReleaseAudit(unittest.TestCase):
    def fixture(self):
        original={'reviewed_project_heads':{'kernel/xiaomi/klimt':'a'*40},
                  'candidate_evidence':{'kernel_audit':{'path':'old.json','sha256':'1'*64}}}
        old=dict(source_heads={'kernel/xiaomi/klimt':'a'*40},baseline_manifest_sha256='b'*64,normalized_config_sha256='c'*64)
        data={'old.json':old,'new.json':copy.deepcopy(old)}
        context=dict(source_snapshot_sha256='d'*64,original_ready_sha256='e'*64,build_exit_sha256='f'*64,
                     archive_sha256='2'*64,tooling_sha256={'release_audit.py':'3'*64})
        update=dict(schema=1,automatic=True,context=context,kernel_audit_previous_sha256='1'*64,
                    kernel_audit_update={'path':'new.json','sha256':'4'*64})
        return original,data,context,update

    def test_automatic_postbuild_update_keeps_original_admission_and_source(self):
        original,data,context,update=self.fixture();before=copy.deepcopy(original);calls=[]
        result=gate.validate_update(update,context,original,lambda r:data[r['path']],lambda r,h:calls.append(h))
        self.assertEqual(original,before);self.assertTrue(result['verification_only'])
        self.assertEqual(result['candidate_evidence']['kernel_audit'],update['kernel_audit_update']);self.assertEqual(len(calls),1)

    def test_changed_source_build_tools_manual_mode_or_config_cannot_auto_admit(self):
        original,data,context,update=self.fixture()
        for field in context:
            wrong=copy.deepcopy(update);wrong['context'][field]='changed'
            with self.subTest(field=field),self.assertRaises(ValueError):
                gate.validate_update(wrong,context,original,lambda r:data[r['path']],lambda *a:None)
        wrong=copy.deepcopy(update);wrong['automatic']=False
        with self.assertRaises(ValueError):gate.validate_update(wrong,context,original,lambda r:data[r['path']],lambda *a:None)
        data['new.json']['normalized_config_sha256']='9'*64
        with self.assertRaisesRegex(ValueError,'configuration policy'):
            gate.validate_update(update,context,original,lambda r:data[r['path']],lambda *a:None)

    def test_compiled_vendor_contract_rechecks_layout_and_new_unresolved_symbols(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'Module.symvers';p.write_text('0x11\tmodule_layout\n0x17\tsymbol\n')
            contract=dict(vendor_count=1,baseline_module_layout=17,baseline_unresolved=['old_unresolved'],exports=[],
                          modules={'stock.ko':{'versions':{'module_layout':17,'symbol':23,'old_unresolved':0}}})
            self.assertTrue(gate.compare_vendor_contract(p,contract)['pass'])
            p.write_text('0x12\tmodule_layout\n0x17\tsymbol\n')
            with self.assertRaises(ValueError):gate.compare_vendor_contract(p,contract)
            p.write_text('0x11\tmodule_layout\n0x17\tsymbol\n');contract['modules']['stock.ko']['versions']['new_unresolved']=1
            with self.assertRaises(ValueError):gate.compare_vendor_contract(p,contract)

    def test_callback_dump_preserves_exact_type_definitions(self):
        parts=['struct first {};\n','struct second {};\n'];baseline='\n'.join(parts)
        self.assertEqual(gate.callback_dump(parts,baseline),baseline)
        with self.assertRaises(ValueError):gate.callback_dump(['struct changed {};\n',parts[1]],baseline)

    def test_own_whitelist_cannot_supply_official_membership(self):
        names='android/abi_gki_aarch64\nandroid/abi_gki_aarch64_klimt\nandroid/abi_gki_aarch64.stg\n'
        with patch('release_audit.subprocess.check_output',side_effect=[names,'[abi_symbol_list]\ntracked # comment\n']) as read:
            tracked=gate.tracked_symbols('/isolated','a'*40)
        self.assertEqual(tracked,{'tracked'});self.assertEqual(read.call_count,2)
        self.assertEqual(gate.membership({'tracked'},tracked,tracked)['tracked_target'],1)
        with self.assertRaises(ValueError):gate.membership({'own_only'},tracked,tracked)

    def test_postbuild_orchestration_generates_once_and_binds_the_owned_attempt(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);attempt=root/'20261111-attempt99';attempt.mkdir()
            old=root/'old.json';old.write_text(json.dumps(dict(baseline_manifest_sha256='b'*64,normalized_config_sha256='c'*64,
                                                             source_heads={'kernel/xiaomi/klimt':'a'*40})))
            prep=root/'prep.json';prep.write_text(json.dumps({'baseline_sha256':'b'*64}))
            original=dict(build='20261111',reviewed_project_heads={'kernel/xiaomi/klimt':'a'*40},candidate_evidence={
                'kernel_audit':candidate_gates.file_record(old),'preparation':candidate_gates.file_record(prep)})
            (attempt/'BUILD_READY.json').write_text(json.dumps(original))
            (attempt/'build-exit.json').write_text(json.dumps({'exit':0,'zip_sha256':'9'*64}))
            manifest='<manifest><project path="kernel/xiaomi/klimt" revision="'+('a'*40)+'"/></manifest>'
            for name in ('prebuild.xml','postbuild.xml'):(attempt/name).write_text(manifest)
            def produce(record,ready,obj,destination,source,ctx):
                destination.mkdir(parents=True);result=destination/'kernel-audit.json';result.write_text(old.read_text());return result
            validator=gate.validate_update
            with patch('controller.ready_heads',lambda r:r['reviewed_project_heads']),patch('controller.live_heads'),\
                 patch('controller.require_tooling_frozen') as frozen,patch('controller.tooling_hashes',return_value={'producer.py':'reviewed'}),\
                 patch('paths.for_build',return_value={'debug':root/'debug'}),patch('release_audit.produce',side_effect=produce) as build,\
                 patch('release_audit.validate_update',side_effect=lambda *a:validator(*a,validate_candidate=lambda *a:None)):
                result=gate.prepare_for_attempt(attempt)
                self.assertTrue(result.is_file());self.assertEqual(build.call_count,1)
                self.assertEqual(gate.prepare_for_attempt(attempt),result);self.assertEqual(build.call_count,1)
                update=json.loads((attempt/'release-audit-update.json').read_text())
                self.assertTrue(update['automatic']);self.assertEqual(update['context']['archive_sha256'],'9'*64)
                self.assertGreaterEqual(frozen.call_count,2)
                (attempt/'build-exit.json').write_text(json.dumps({'exit':1,'zip_sha256':'9'*64}))
                with self.assertRaises(ValueError):gate.effective_ready(attempt,original)
