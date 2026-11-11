import copy
import gzip
import struct
import unittest
from unittest.mock import patch

import candidate_gates
import kernel_artifact as gate


class Artifact(unittest.TestCase):
    def image(self, config=b'CONFIG_LTO_NONE=y\nCONFIG_LOCALVERSION="-trial"\n'):
        image=bytearray(64);image[56:60]=b'ARM\x64'
        return bytes(image)+b'same expected Linux banner\0IKCFG_ST'+gzip.compress(config)+b'IKCFG_ED'

    def config_hash(self):
        return gate.digest(candidate_gates.normalized_config('CONFIG_LTO_NONE=y\n').encode())

    def test_packaged_image_and_embedded_config_are_both_checked(self):
        image=self.image()
        config,digest=gate.check_image(image,image,self.config_hash())
        self.assertIn(b'CONFIG_LTO_NONE=y',config)
        self.assertEqual(digest,self.config_hash())

    def test_same_banner_and_correct_output_config_cannot_mask_stale_payload(self):
        audited=self.image();stale=audited[:64]+b'changed code'+audited[64:]
        self.assertIn(b'same expected Linux banner',stale)
        self.assertEqual(gate.embedded_config(stale),gate.embedded_config(audited))
        with self.assertRaisesRegex(ValueError,'differs from audited'):
            gate.check_image(stale,audited,self.config_hash())

    def test_embedded_config_drift_is_rejected_even_when_elf_bytes_match(self):
        image=self.image(b'CONFIG_LTO_CLANG=y\n')
        with self.assertRaisesRegex(ValueError,'IKCONFIG differs'):
            gate.check_image(image,image,self.config_hash())

    def test_boot_header_bounds_and_raw_kernel_compression(self):
        image=self.image();payload=gzip.compress(image);boot=bytearray(4096)
        boot[:8]=b'ANDROID!';struct.pack_into('<I',boot,8,len(payload));struct.pack_into('<I',boot,20,1584);struct.pack_into('<I',boot,40,4)
        self.assertEqual(gate.raw_image(gate.boot_payload(bytes(boot)+payload)),image)
        with self.assertRaises(ValueError):gate.boot_payload(bytes(boot)+payload[:-1])
        with self.assertRaises(ValueError):gate.raw_image(b'unknown')

    def test_module_signatures_do_not_hide_changed_elf_bytes(self):
        raw=b'\x7fELF audited code';signature=b'certificate signature'
        footer=b'\0\0\2\0\0\0\0\0'+len(signature).to_bytes(4,'big')
        signed=raw+signature+footer+gate.SIGNATURE_MAGIC
        signed=signed+signature+footer+gate.SIGNATURE_MAGIC
        self.assertEqual(gate.unsigned_module(signed),(raw,2))
        with self.assertRaises(ValueError):gate.unsigned_module(raw+bytes(12)+gate.SIGNATURE_MAGIC)
        self.assertNotEqual(gate.unsigned_module(signed.replace(b'audited',b'changed'))[0],raw)

    def test_promotion_rejects_stale_boot_archive_config_and_module_records(self):
        kernel={'path':'vmlinux','sha256':'a'*64};modules=[{'path':'test.ko','sha256':'b'*64}]
        frozen={'kernel/xiaomi/klimt':'c'*40};audit={'normalized_config_sha256':'d'*64}
        binding=dict(schema=1,**{'pass':True},source_kernel='c'*40,archive_sha256='e'*64,
                     audited_vmlinux_sha256='a'*64,normalized_config_sha256='d'*64,
                     image_sha256='f'*64,audited_image_sha256='f'*64,boot_image_sha256='1'*64,
                     compressed_kernel_sha256='3'*64,config_sha256='4'*64,image_rule_sha256='5'*64,
                     objcopy_sha256='6'*64,strip_sha256='7'*64,
                     modules=[dict(name='test.ko',audited_sha256='b'*64,packaged_sha256='2'*64,
                                   stripped_sha256='8'*64,signature_envelopes=2)])
        images=[dict(path='boot.img',sha256='1'*64)];files=[dict(path='system_dlkm/lib/modules/test.ko',sha256='2'*64)]
        with patch('kernel_artifact.audited_inputs',return_value=(kernel,modules)):
            gate.validate_receipt(binding,audit,frozen,'e'*64,images,files)
            for field in ('archive_sha256','boot_image_sha256','audited_vmlinux_sha256','normalized_config_sha256','image_sha256'):
                changed=copy.deepcopy(binding);changed[field]='9'*64
                with self.subTest(field=field),self.assertRaises(ValueError):
                    gate.validate_receipt(changed,audit,frozen,'e'*64,images,files)
            changed=copy.deepcopy(binding);changed['modules'][0]['packaged_sha256']='9'*64
            with self.assertRaises(ValueError):gate.validate_receipt(changed,audit,frozen,'e'*64,images,files)
            changed=copy.deepcopy(binding);del changed['image_sha256'];del changed['audited_image_sha256']
            with self.assertRaises(ValueError):gate.validate_receipt(changed,audit,frozen,'e'*64,images,files)
