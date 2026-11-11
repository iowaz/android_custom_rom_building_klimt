"""Bind packaged kernel/module bytes to the exact debug ELFs whose ABI was audited."""
import gzip
import hashlib
import json
from pathlib import Path
import re
import shlex
import struct
import subprocess
import zlib

import candidate_gates
import elf_contract
import paths
import rollback_security
import vendor_boot_contract

IMAGE_FLAGS = ['-O', 'binary', '-R', '.note', '-R', '.note.gnu.build-id', '-R', '.comment', '-S']
SIGNATURE_MAGIC = b'~Module signature appended~\n'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def boot_payload(boot):
    if len(boot) < 4096 or boot[:8] != b'ANDROID!':
        raise ValueError('Expected an Android boot v4 image')
    size = struct.unpack_from('<I', boot, 8)[0]
    if struct.unpack_from('<I', boot, 40)[0] != 4 or struct.unpack_from('<I', boot, 20)[0] != 1584:
        raise ValueError('Expected the frozen v4 boot header layout')
    if not size or 4096+size > len(boot):
        raise ValueError('Truncated or empty packaged kernel')
    return boot[4096:4096+size]


def raw_image(payload):
    if payload.startswith(b'\x1f\x8b\x08'):
        return gzip.decompress(payload)
    if payload[:4] in (b'\x02\x21\x4c\x18', b'\x04\x22\x4d\x18'):
        return subprocess.check_output(['lz4', '-d', '-c'], input=payload, stderr=subprocess.PIPE)
    if len(payload) >= 64 and payload[56:60] == b'ARM\x64':
        return payload
    raise ValueError('Unsupported packaged arm64 kernel compression/header')


def embedded_config(image):
    marker = b'IKCFG_ST\x1f\x8b\x08'
    if image.count(marker) != 1:
        raise ValueError('Unique embedded IKCONFIG is required')
    decoder = zlib.decompressobj(31)
    config = decoder.decompress(image[image.index(marker)+8:], 4*1024*1024+1)
    if not decoder.eof or len(config) > 4*1024*1024 or not decoder.unused_data.startswith(b'IKCFG_ED'):
        raise ValueError('Invalid or oversized embedded IKCONFIG')
    return config


def check_image(packaged, audited, expected_config):
    if packaged != audited:
        raise ValueError('Packaged kernel differs from audited vmlinux-derived Image')
    config = embedded_config(packaged)
    normalized = digest(candidate_gates.normalized_config(config.decode()).encode())
    if normalized != expected_config:
        raise ValueError('Packaged IKCONFIG differs from the audited configuration')
    return config, normalized


def unsigned_module(module):
    """Remove only structurally bounded appended PKCS#7 envelopes, never ELF bytes."""
    count = 0
    while module.endswith(SIGNATURE_MAGIC):
        if count == 8 or len(module) < len(SIGNATURE_MAGIC)+12:
            raise ValueError('Invalid module signature envelope')
        end = len(module)-len(SIGNATURE_MAGIC)
        footer = module[end-12:end]
        length = int.from_bytes(footer[8:12], 'big')
        start = end-12-length-footer[3]-footer[4]
        if footer[2] != 2 or footer[5:8] != b'\0'*3 or not length or start <= 0:
            raise ValueError('Invalid module signature envelope')
        module = module[:start]
        count += 1
    return module, count


def audited_inputs(audit):
    files = audit['checks']['type_abi']['files']
    matches = [r for r in files if Path(r['path']).name == 'abi-RESULT.json']
    if len(matches) != 1:
        raise ValueError('Unique audited ABI result required')
    result = candidate_gates.revalidate(matches[0])
    inputs = result['inputs']['new']['inputs']
    proofs = {(r['path'], r['sha256']) for r in files}
    if not inputs or any((r['path'], r['sha256']) not in proofs for r in inputs):
        raise ValueError('Audited ELF inputs are not individually hash-bound')
    for record in inputs:
        if rollback_security.digest(record['path']) != record['sha256']:
            raise ValueError('Audited ELF hash drift')
    kernels = [r for r in inputs if Path(r['path']).name == 'vmlinux']
    modules = [r for r in inputs if Path(r['path']).suffix == '.ko']
    if len(kernels) != 1 or not modules or len({Path(r['path']).name for r in modules}) != len(modules):
        raise ValueError('Incomplete/ambiguous audited kernel/module inputs')
    return kernels[0], modules


def audited_symvers(audit):
    records = [r for r in audit['checks']['module_crc']['files'] if Path(r['path']).name == 'Module.symvers']
    if len(records) != 1 or not Path(records[0]['path']).resolve().is_relative_to(paths.DIAGNOSTICS.resolve()):
        raise ValueError('A unique preserved release Module.symvers is required')
    if rollback_security.digest(records[0]['path']) != records[0]['sha256']:
        raise ValueError('Preserved release Module.symvers changed')
    return Path(records[0]['path'])


def compare_module(name, module, expected, audited_sha256):
    unsigned, signatures = unsigned_module(module)
    if expected != unsigned:
        raise ValueError('Packaged GKI module differs from audited ELF: '+name)
    return dict(name=name,audited_sha256=audited_sha256,packaged_sha256=digest(module),
                stripped_sha256=digest(expected),signature_envelopes=signatures)


def validate(audit, frozen, boot_path, module_directory, archive_sha256, source):
    source = Path(source)
    if any(not Path(r['path']).resolve().is_relative_to(paths.DIAGNOSTICS.resolve())
           for c in audit['checks'].values() for r in c['files']):
        raise ValueError('Packaged candidate requires all audit proofs preserved in release diagnostics')
    kernel, modules = audited_inputs(audit)
    crc_contract = elf_contract.validate(audited_symvers(audit), [kernel['path'],*[r['path'] for r in modules]])
    makefile = subprocess.check_output(['git', '-C', str(source/'kernel/xiaomi/klimt'), 'show',
                                       frozen['kernel/xiaomi/klimt']+':arch/arm64/boot/Makefile'], text=True)
    rules = [l.split(':=', 1)[1] for l in makefile.splitlines() if l.startswith('OBJCOPYFLAGS_Image :=')]
    if len(rules) != 1 or shlex.split(rules[0]) != IMAGE_FLAGS:
        raise ValueError('Unreviewed frozen kernel Image conversion rule')
    # This pinned prebuilt is a deterministic ELF conversion tool, not a compiler-policy selection.
    tools = source/'prebuilts/clang/host/linux-x86/clang-r596125/bin'
    objcopy, strip = tools/'llvm-objcopy', tools/'llvm-strip'
    audited = subprocess.check_output([str(objcopy), *IMAGE_FLAGS, kernel['path'], '-'])
    boot = Path(boot_path).read_bytes()
    payload = boot_payload(boot)
    image = raw_image(payload)
    config, normalized = check_image(image, audited, audit['normalized_config_sha256'])
    packaged = {p.name:p for p in Path(module_directory).rglob('*.ko')}
    if len(packaged) != len(list(Path(module_directory).rglob('*.ko'))) or set(packaged) != {Path(r['path']).name for r in modules}:
        raise ValueError('Packaged source-built GKI module set differs from audited ELFs')
    module_records = []
    stripped = {}
    module_inputs = {Path(r['path']).name:r for r in modules}
    for record in modules:
        name = Path(record['path']).name
        original = packaged[name].read_bytes()
        expected = subprocess.check_output([str(strip), '--strip-debug', '-o', '-', record['path']])
        stripped[name] = expected
        module_records.append(compare_module(name,original,expected,record['sha256']))
    vendor_boot = Path(boot_path).with_name('vendor_boot.img').read_bytes()
    ramdisk_count, ramdisk_modules = vendor_boot_contract.bind(vendor_boot,module_inputs,
        lambda name,body: compare_module(name,body,stripped[name],module_inputs[name]['sha256']))
    return dict(schema=1, **{'pass':True}, source_kernel=frozen['kernel/xiaomi/klimt'], archive_sha256=archive_sha256,
                boot_image_sha256=digest(boot), compressed_kernel_sha256=digest(payload), image_sha256=digest(image),
                audited_image_sha256=digest(audited), audited_vmlinux_sha256=kernel['sha256'], config_sha256=digest(config),
                normalized_config_sha256=normalized, image_rule_sha256=digest(makefile.encode()),
                objcopy_sha256=rollback_security.digest(objcopy), strip_sha256=rollback_security.digest(strip),
                module_symvers_sha256=crc_contract['symvers_sha256'],elf_crcs_sha256=crc_contract['elf_crcs_sha256'],
                elf_crc_symbols=crc_contract['symbols'],vendor_boot_sha256=digest(vendor_boot),
                vendor_ramdisk_count=ramdisk_count,vendor_boot_modules=ramdisk_modules,modules=module_records)


def validate_receipt(binding, audit, frozen, archive_sha256, images, filesystem):
    kernel, modules = audited_inputs(audit)
    boots = [r for r in images if r['path'] == 'boot.img']
    digests = ('archive_sha256','boot_image_sha256','compressed_kernel_sha256','image_sha256','audited_image_sha256',
               'audited_vmlinux_sha256','config_sha256','normalized_config_sha256','image_rule_sha256',
               'objcopy_sha256','strip_sha256','vendor_boot_sha256','module_symvers_sha256','elf_crcs_sha256')
    vendors = [r for r in images if r['path'] == 'vendor_boot.img']
    symvers = [r for r in audit['checks']['module_crc']['files'] if Path(r['path']).name == 'Module.symvers']
    if (any(not re.fullmatch(r'[0-9a-f]{64}', str(binding.get(k, ''))) for k in digests) or
        binding.get('schema') != 1 or binding.get('pass') is not True or
        binding.get('source_kernel') != frozen['kernel/xiaomi/klimt'] or binding.get('archive_sha256') != archive_sha256 or
        binding.get('audited_vmlinux_sha256') != kernel['sha256'] or
        binding.get('normalized_config_sha256') != audit['normalized_config_sha256'] or
        binding.get('image_sha256') != binding.get('audited_image_sha256') or len(boots) != 1 or
        binding.get('boot_image_sha256') != boots[0]['sha256'] or len(vendors) != 1 or
        binding.get('vendor_boot_sha256') != vendors[0]['sha256'] or len(symvers) != 1 or
        binding.get('module_symvers_sha256') != symvers[0]['sha256'] or
        type(binding.get('elf_crc_symbols')) is not int or binding['elf_crc_symbols'] <= 0):
        raise ValueError('Packaged kernel binding is stale or inconsistent')
    expected = {Path(r['path']).name:r['sha256'] for r in modules}
    entries = binding.get('modules', [])
    installed = {Path(r['path']).name:r['sha256'] for r in filesystem
                 if r['path'].startswith('system_dlkm/') and r['path'].endswith('.ko')}
    if (len(entries) != len(expected) or {r['name'] for r in entries} != set(expected) or
        set(installed) != set(expected) or any(r['audited_sha256'] != expected[r['name']] or
        r['packaged_sha256'] != installed[r['name']] or not re.fullmatch(r'[0-9a-f]{64}',r.get('stripped_sha256','')) or
        type(r.get('signature_envelopes')) is not int or not 0 <= r['signature_envelopes'] <= 8 for r in entries)):
        raise ValueError('Packaged GKI module binding is stale or incomplete')
    ramdisk = binding.get('vendor_boot_modules', [])
    canonical = {r['name']:r for r in entries}
    if (type(binding.get('vendor_ramdisk_count')) is not int or binding['vendor_ramdisk_count'] <= 0 or
        len(ramdisk) != len(vendor_boot_contract.RAMDISK_GKI) or
        {r['name'] for r in ramdisk} != vendor_boot_contract.RAMDISK_GKI or
        len({(r['ramdisk'],r['path']) for r in ramdisk}) != len(ramdisk) or
        any(r['audited_sha256'] != expected[r['name']] or
            r['stripped_sha256'] != canonical[r['name']]['stripped_sha256'] or
            not re.fullmatch(r'[0-9a-f]{64}',r.get('packaged_sha256','')) or
            type(r.get('signature_envelopes')) is not int or not 0 <= r['signature_envelopes'] <= 8 or
            type(r.get('ramdisk')) is not int or not 0 <= r['ramdisk'] < binding['vendor_ramdisk_count'] for r in ramdisk)):
        raise ValueError('Vendor_boot GKI copy binding is stale or incomplete')
