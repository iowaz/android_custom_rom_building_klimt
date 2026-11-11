import gzip
import struct
import unittest

import kernel_artifact
import vendor_boot_contract as gate


def newc(name, body=b'', mode=0o100644):
    name=name.encode()+b'\0';fields=[1,mode,0,0,1,0,len(body),0,0,0,0,len(name),0]
    result=b'070701'+b''.join(f'{x:08x}'.encode() for x in fields)+name
    result+=b'\0'*((-len(result))%4);result+=body;result+=b'\0'*((-len(result))%4)
    return result


def vendor_image(entries):
    archive=b''.join(newc(n,b) for n,b in entries)+newc('TRAILER!!!')
    packed=gzip.compress(archive);align=lambda n:(n+4095)//4096*4096
    table=4096+align(len(packed));image=bytearray(table+108)
    image[:8]=b'VNDRBOOT';struct.pack_into('<II',image,8,4,4096)
    struct.pack_into('<I',image,24,len(packed));struct.pack_into('<II',image,2096,2128,0)
    struct.pack_into('<III',image,2112,108,1,108);struct.pack_into('<II',image,table,len(packed),0)
    image[4096:4096+len(packed)]=packed
    return bytes(image)


class VendorCopies(unittest.TestCase):
    def entries(self):return [('lib/modules/'+n,b'\x7fELF same CRC, audited code') for n in sorted(gate.RAMDISK_GKI)]

    def compare(self,name,body):
        return kernel_artifact.compare_module(name,body,b'\x7fELF same CRC, audited code','a'*64)

    def test_every_first_stage_copy_is_bound(self):
        count,copies=gate.bind(vendor_image(self.entries()),gate.RAMDISK_GKI,self.compare)
        self.assertEqual(count,1);self.assertEqual({r['name'] for r in copies},gate.RAMDISK_GKI)
        self.assertTrue(all(r['ramdisk']==0 for r in copies))

    def test_same_crc_stale_first_stage_copy_is_rejected(self):
        entries=self.entries();entries[0]=(entries[0][0],b'\x7fELF same CRC, stale code')
        with self.assertRaisesRegex(ValueError,'differs from audited'):
            gate.bind(vendor_image(entries),gate.RAMDISK_GKI,self.compare)

    def test_missing_duplicate_or_invalid_ramdisk_copies_are_rejected(self):
        for entries in (self.entries()[:-1],self.entries()+[self.entries()[0]]):
            with self.assertRaises(ValueError):gate.bind(vendor_image(entries),gate.RAMDISK_GKI,self.compare)
        image=bytearray(vendor_image(self.entries()));struct.pack_into('<I',image,2116,1000)
        with self.assertRaises(ValueError):gate.ramdisks(bytes(image))
        with self.assertRaises(ValueError):list(gate.members(newc('../outside.ko',b'bad')))
