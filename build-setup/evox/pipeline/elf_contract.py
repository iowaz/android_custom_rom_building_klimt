"""Read arm64 ELF export CRCs without trusting a separate Module.symvers producer."""
import hashlib
import json
from pathlib import Path
import struct


def export_crcs(data):
    if (len(data) < 64 or data[:6] != b'\x7fELF\x02\x01' or
        struct.unpack_from('<H', data, 18)[0] != 183):
        raise ValueError('Expected a little-endian ELF64 arm64 kernel/module')
    offset = struct.unpack_from('<Q', data, 40)[0]
    size, count = struct.unpack_from('<HH', data, 58)
    if size != 64 or not count or offset+size*count > len(data):
        raise ValueError('Invalid ELF section table')
    sections = [struct.unpack_from('<IIQQQQIIQQ', data, offset+i*size) for i in range(count)]
    result = {}
    for section in sections:
        if section[1] != 2:  # SHT_SYMTAB
            continue
        if section[9] != 24 or section[5] % 24 or section[6] >= count or section[4]+section[5] > len(data):
            raise ValueError('Invalid ELF symbol table')
        strings = sections[section[6]]
        if strings[4]+strings[5] > len(data):
            raise ValueError('Invalid ELF string table')
        names = data[strings[4]:strings[4]+strings[5]]
        for pos in range(section[4], section[4]+section[5], 24):
            name, _, _, index, value, _ = struct.unpack_from('<IBBHQQ', data, pos)
            if name >= len(names):
                raise ValueError('Invalid ELF symbol name')
            end = names.find(b'\0', name)
            if end < 0:
                raise ValueError('Unterminated ELF symbol name')
            symbol = names[name:end].decode(errors='surrogateescape')
            if not symbol.startswith('__crc_'):
                continue
            if index == 0xfff1:  # SHN_ABS
                crc = value & 0xffffffff
            elif 0 < index < count:
                provider = sections[index]
                relative = value-provider[3]
                location = provider[4]+relative
                if provider[1] == 8 or relative < 0 or relative+4 > provider[5] or location+4 > len(data):
                    raise ValueError('Invalid ELF export CRC location')
                crc = struct.unpack_from('<I', data, location)[0]
            else:
                raise ValueError('Unsupported ELF export CRC section')
            result[symbol[6:]] = crc
    return result


def validate(symvers, elfs):
    expected = {p[1]:int(p[0],16) for line in Path(symvers).read_text().splitlines() if len(p:=line.split()) >= 2}
    actual = {}
    for path in elfs:
        for name, crc in export_crcs(Path(path).read_bytes()).items():
            if name in actual and actual[name] != crc:
                raise ValueError('Conflicting ELF export CRC: '+name)
            actual[name] = crc
    if not expected or actual != expected:
        missing = sorted(set(expected)-set(actual))
        changed = sorted(k for k in expected.keys() & actual.keys() if expected[k] != actual[k])
        raise ValueError('Module.symvers differs from audited ELF CRCs: missing='+str(missing[:12])+' changed='+str(changed[:12]))
    return dict(**{'pass':True}, symbols=len(actual),
                elf_crcs_sha256=hashlib.sha256(json.dumps(actual,sort_keys=True).encode()).hexdigest(),
                symvers_sha256=hashlib.sha256(Path(symvers).read_bytes()).hexdigest())
