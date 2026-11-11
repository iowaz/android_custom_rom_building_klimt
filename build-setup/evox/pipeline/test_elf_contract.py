from pathlib import Path
import struct
import tempfile
import unittest

import elf_contract as gate


def elf(crc=0x12345678, absolute=False):
    data=bytearray(512);data[:6]=b'\x7fELF\x02\x01';struct.pack_into('<H',data,18,183)
    struct.pack_into('<Q',data,40,256);struct.pack_into('<HH',data,58,64,4)
    struct.pack_into('<I',data,64,crc);names=b'\0__crc_symbol\0';data[72:72+len(names)]=names
    struct.pack_into('<IBBHQQ',data,120,1,0,0,0xfff1 if absolute else 1,crc if absolute else 0x1000,4)
    sections=[(0,0,0,0,0,0,0,0,0,0),(0,1,2,0x1000,64,4,0,0,4,0),
              (0,3,0,0,72,len(names),0,0,1,0),(0,2,0,0,96,48,2,0,8,24)]
    for i,section in enumerate(sections):struct.pack_into('<IIQQQQIIQQ',data,256+i*64,*section)
    return bytes(data)


class Crcs(unittest.TestCase):
    def test_section_and_absolute_export_crc_symbols(self):
        for absolute in (False,True):self.assertEqual(gate.export_crcs(elf(absolute=absolute)),{'symbol':0x12345678})

    def test_text_symvers_cannot_mask_different_audited_elf_crc(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);symbols=root/'Module.symvers';symbols.write_text('0x12345678\tsymbol\n')
            image=root/'vmlinux';image.write_bytes(elf())
            self.assertEqual(gate.validate(symbols,[image])['symbols'],1)
            image.write_bytes(elf(0x87654321))
            with self.assertRaisesRegex(ValueError,'differs from audited ELF'):gate.validate(symbols,[image])

    def test_malformed_elf_fails_closed(self):
        with self.assertRaises(ValueError):gate.export_crcs(b'bad ELF')
        data=bytearray(elf());struct.pack_into('<Q',data,40,len(data)+1)
        with self.assertRaises(ValueError):gate.export_crcs(bytes(data))
