"""Inspect every source-built GKI copy directly inside the packaged vendor_boot image."""
import gzip
from pathlib import PurePosixPath
import struct
import subprocess

RAMDISK_GKI = {'libarc4.ko','zram.ko','rfkill.ko','zsmalloc.ko'}


def ramdisks(image):
    if len(image) < 2128 or image[:8] != b'VNDRBOOT':
        raise ValueError('Expected vendor_boot v4')
    version, page = struct.unpack_from('<II', image, 8)
    ramdisk_size = struct.unpack_from('<I', image, 24)[0]
    header_size, dtb_size = struct.unpack_from('<II', image, 2096)
    table_size, count, entry_size = struct.unpack_from('<III', image, 2112)
    if version != 4 or page != 4096 or header_size != 2128 or not 0 < count <= 256 or entry_size < 108:
        raise ValueError('Unreviewed vendor_boot header/table layout')
    align = lambda n: (n+page-1)//page*page
    start = align(header_size)
    table = start+align(ramdisk_size)+align(dtb_size)
    if table_size != count*entry_size or table+table_size > len(image) or start+ramdisk_size > len(image):
        raise ValueError('Truncated vendor_boot ramdisk table')
    result = []
    intervals = []
    for index in range(count):
        size, offset = struct.unpack_from('<II', image, table+index*entry_size)
        if not size or offset+size > ramdisk_size or any(offset < b and a < offset+size for a,b in intervals):
            raise ValueError('Invalid/overlapping vendor_boot ramdisk')
        intervals.append((offset,offset+size))
        payload = image[start+offset:start+offset+size]
        if payload.startswith(b'\x1f\x8b\x08'):
            payload = gzip.decompress(payload)
        elif payload[:4] in (b'\x02\x21\x4c\x18', b'\x04\x22\x4d\x18'):
            payload = subprocess.check_output(['lz4','-d','-c'], input=payload, stderr=subprocess.PIPE)
        if len(payload) > 512*1024*1024:
            raise ValueError('Vendor ramdisk exceeds inspection bound')
        result.append((index,payload))
    return result


def members(data):
    pos = 0
    while pos < len(data):
        while pos < len(data) and data[pos] == 0:
            pos += 1
        if pos == len(data):
            return
        if pos+110 > len(data) or data[pos:pos+6] not in (b'070701',b'070702'):
            raise ValueError('Invalid vendor ramdisk newc header')
        fields = [int(data[pos+6+i*8:pos+14+i*8],16) for i in range(13)]
        mode, size, name_size = fields[1],fields[6],fields[11]
        if not 0 < name_size <= 4096 or pos+110+name_size > len(data):
            raise ValueError('Invalid vendor ramdisk member name')
        name = data[pos+110:pos+110+name_size]
        if not name.endswith(b'\0'):
            raise ValueError('Unterminated vendor ramdisk member name')
        name = name[:-1].decode(errors='surrogateescape')
        body = (pos+110+name_size+3)&~3
        if body+size > len(data):
            raise ValueError('Truncated vendor ramdisk member')
        contents = data[body:body+size]
        pos = (body+size+3)&~3
        if name == 'TRAILER!!!':
            continue
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('Invalid vendor ramdisk member path')
        yield str(path),mode,contents


def bind(image, audited, compare, required=RAMDISK_GKI):
    copies = []
    chunks = ramdisks(image)
    for index, archive in chunks:
        for path, mode, contents in members(archive):
            name = PurePosixPath(path).name
            if name not in audited:
                continue
            if mode & 0o170000 != 0o100000:
                raise ValueError('Audited ramdisk GKI module must be a regular file')
            copies.append(dict(compare(name,contents),ramdisk=index,path=path))
    if {r['name'] for r in copies} != set(required) or len(copies) != len(required):
        raise ValueError('Source-built vendor_boot GKI copy set changed')
    return len(chunks),copies
