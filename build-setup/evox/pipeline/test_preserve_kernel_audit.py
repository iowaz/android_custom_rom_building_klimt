import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import preserve_kernel_audit as gate


class Preserve(unittest.TestCase):
    def test_preserved_inputs_survive_removal_of_original_build_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);live=root/'live';live.mkdir();elf=live/'vmlinux';elf.write_bytes(b'audited ELF')
            record=lambda p:dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
            executed_path=str(root/'overwritten-output/vmlinux')
            proof=live/'abi-RESULT.json';proof.write_text(json.dumps({'inputs':[dict(record(elf),path=executed_path)],'argv':[executed_path]}))
            audit=root/'audit.json';audit.write_text(json.dumps({'checks':{'type_abi':{'files':[record(elf),record(proof)]}}}))
            diagnostics=root/'diagnostics'
            with patch('paths.DIAGNOSTICS',diagnostics):out=gate.preserve(audit,diagnostics/'release')
            elf.unlink();proof.unlink();live.rmdir()
            saved=json.loads(out.read_text());files=saved['checks']['type_abi']['files']
            self.assertTrue(all(hashlib.sha256(Path(r['path']).read_bytes()).hexdigest()==r['sha256'] for r in files))
            abi=json.loads(next(Path(r['path']).read_text() for r in files if Path(r['path']).name=='abi-RESULT.json'))
            self.assertEqual(Path(abi['inputs'][0]['path']).read_bytes(),b'audited ELF')
            self.assertEqual(abi['argv'],[executed_path])  # executed command remains accurate historical provenance

    def test_changed_proof_is_rejected_during_preservation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);proof=root/'proof';proof.write_text('changed')
            audit=root/'audit.json';audit.write_text(json.dumps({'checks':{'x':{'files':[dict(path=str(proof),sha256='0'*64)]}}}))
            with patch('paths.DIAGNOSTICS',root/'diag'),self.assertRaises(ValueError):
                gate.preserve(audit,root/'diag/release')
