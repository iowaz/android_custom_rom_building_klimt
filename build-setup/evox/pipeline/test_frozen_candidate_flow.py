import contextlib
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import controller
import frozen_candidate
import kernel_contract
import paths
import prepare


class CandidateFlow(unittest.TestCase):
    def flow(self, dry=False, foreign=False):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name)
        source=root/'src';source.mkdir();audit=root/'audit.git';audit.mkdir();logs=root/'logs';logs.mkdir()
        snapshot=root/'control.xml';snapshot.write_text('<manifest/>')
        old={kernel_contract.KERNEL:'a'*40,kernel_contract.DEVICE:'b'*40,'frameworks/base':'c'*40}
        changes={kernel_contract.KERNEL:'d'*40,kernel_contract.DEVICE:'e'*40}
        actual=dict(old,**{kernel_contract.DEVICE:changes[kernel_contract.DEVICE]})
        calls=[];tooling={'reviewed.py':'f'*64}
        spec=root/'spec.json';spec.write_text(json.dumps(dict(schema=1,baseline_sha256=prepare.sha256(snapshot),
             heads=changes,audit_repository=str(audit),tooling_sha256=tooling)))
        prep=SimpleNamespace(snapshot=snapshot,out=root/'preparation',build='20261112',previous='20261111',dry=dry,
                             bundle=lambda rev:{'frameworks/base':{'base':'0'*40,'final_head':'c'*40}})
        def audit_git(argv,**kwargs):
            args=argv[2:]
            if args[0]=='rev-parse':return changes[kernel_contract.KERNEL]+'\n'
            if args[0]=='show':return 'frozen kernel metadata\n'
            raise AssertionError(args)
        def source_git(project,*args,**kwargs):
            calls.append(args)
            if args[0]=='show':return 'frozen device metadata'
            if args[0]=='fetch':return ''
            if args[:2]==('checkout','--detach'):
                actual[kernel_contract.KERNEL]=args[2];return ''
            raise AssertionError(args)
        def live(expected):self.assertEqual(expected,actual)
        layout=lambda b:dict(logs=logs/b,preparation=root/'previous'/b)
        with contextlib.ExitStack() as stack:
            mocks={'prepare.S':source,'prepare.M':root/'manifests','prepare.git':source_git,'prepare.clean':lambda p:None,
                   'controller.manifest_heads':lambda b:copy.deepcopy(old),'controller.expected_heads':lambda f:copy.deepcopy(f),
                   'controller.tooling_hashes':lambda:tooling,'controller.live_heads':live,
                   'controller.foreign_processes':lambda:['active'] if foreign else [],
                   'controller.lock':lambda p:contextlib.nullcontext(), 'paths.LOGS':logs,'paths.for_build':layout,
                   'frozen_candidate.subprocess.check_output':audit_git,
                   'frozen_candidate.subprocess.run':lambda *a,**kw:SimpleNamespace(returncode=0,stdout='FINAL frameworks/base\n',stderr=''),
                   'kernel_contract.derive':lambda *args:None}
            for name,value in mocks.items():stack.enter_context(patch(name,value))
            if foreign:
                with self.assertRaisesRegex(RuntimeError,'build/extraction'):frozen_candidate.run(prep,spec)
            else:frozen_candidate.run(prep,spec)
        return prep,calls,changes

    def test_full_candidate_flow_fetches_exact_commit_detached_and_records_control(self):
        prep,calls,changes=self.flow()
        record=json.loads((prep.out/'CANDIDATE.json').read_text())
        self.assertEqual(record['heads'],changes)
        self.assertEqual(record['effective_control_heads'][kernel_contract.KERNEL],'a'*40)
        self.assertFalse(record['published'])
        self.assertTrue(any(c[0]=='fetch' and c[-1]==changes[kernel_contract.KERNEL] for c in calls))
        self.assertIn(('checkout','--detach',changes[kernel_contract.KERNEL]),calls)
        self.assertFalse(any(c[0] in ('reset','push') for c in calls))

    def test_dry_preflight_and_foreign_owner_never_checkout_or_record(self):
        for dry,foreign in ((True,False),(False,True)):
            with self.subTest(dry=dry,foreign=foreign):
                prep,calls,_=self.flow(dry,foreign)
                self.assertFalse(any(c[0] in ('fetch','checkout') for c in calls))
                self.assertFalse((prep.out/'CANDIDATE.json').exists())

    def test_candidate_step_gating_blocks_sync_and_requires_label_before_freeze(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'.repo').mkdir();out=root/'preparation';out.mkdir();(out/'CANDIDATE.json').write_text('{}')
            prep=prepare.Prep.__new__(prepare.Prep)
            prep.out=out;prep.build='20261112';prep.previous='20261111';prep.dry=False
            with patch('prepare.S',root),patch('prepare.clean'),patch('frozen_candidate.check_record'):
                for step in ('upstream','move-renamed','sync','patch'):
                    with self.subTest(step=step),self.assertRaisesRegex(RuntimeError,'forbids'):
                        prep.require(step)
                prep.require('label')
                with self.assertRaisesRegex(RuntimeError,'label'):prep.require('freeze')
                (out/'LABEL.json').write_text('{}');prep.require('freeze')
