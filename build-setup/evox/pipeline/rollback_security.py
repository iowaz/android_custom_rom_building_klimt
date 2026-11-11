"""Mechanical equality of emitted rollback/security metadata across controlled candidates."""
import hashlib
import json
import re
import struct
import subprocess
from pathlib import Path

IMAGES = ('boot', 'init_boot', 'vendor_boot', 'dtbo', 'vbmeta', 'vbmeta_system', 'vbmeta_vendor',
          'system', 'system_ext', 'product', 'vendor', 'odm', 'system_dlkm', 'vendor_dlkm', 'odm_dlkm')
PROPS = {'system': 'system/system/build.prop', 'system_ext': 'system_ext/etc/build.prop',
         'product': 'product/etc/build.prop', 'vendor': 'vendor/build.prop', 'odm': 'odm/etc/build.prop',
         'system_dlkm': 'system_dlkm/etc/build.prop', 'vendor_dlkm': 'vendor_dlkm/etc/build.prop',
         'odm_dlkm': 'odm_dlkm/etc/build.prop'}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(4*1024*1024), b''):
            h.update(b)
    return h.hexdigest()


def parse_avb(text):
    def field(name):
        found = re.findall(r'^'+re.escape(name)+r':\s*(.*?)\s*$', text, re.M)
        if len(found) != 1:
            raise ValueError('Missing/duplicate AVB header: '+name)
        return found[0]
    result = {k: field(k) for k in ('Rollback Index', 'Rollback Index Location', 'Flags', 'Algorithm')}
    result['Public key (sha1)'] = None if result['Algorithm'] == 'NONE' else field('Public key (sha1)')
    props = re.findall(r"^    Prop: ([^ ]+) -> '(.*)'$", text, re.M)
    security = [(k,v) for k,v in props if k.endswith(('.security_patch', '.os_version'))]
    if len(dict(security)) != len(security):
        raise ValueError('Duplicate AVB security property')
    result['security_properties'] = dict(security)
    chains = []
    for block in text.split('    Chain Partition descriptor:')[1:]:
        name = re.search(r'^      Partition Name:\s*(\S+)', block, re.M)
        location = re.search(r'^      Rollback Index Location:\s*(\d+)', block, re.M)
        key = re.search(r'^      Public key \(sha1\):\s*(\S+)', block, re.M)
        if not all((name,location,key)):
            raise ValueError('Malformed AVB chain descriptor')
        chains.append((name[1], int(location[1]), key[1]))
    if len({c[0] for c in chains}) != len(chains):
        raise ValueError('Duplicate AVB chain partition')
    result['chain_partitions'] = [list(chain) for chain in sorted(chains)]
    return result


def boot_header(path):
    with Path(path).open('rb') as f:
        data = f.read(48)
    if data[:8] != b'ANDROID!':
        raise ValueError('Invalid Android boot header: '+str(path))
    header = struct.unpack_from('<I', data, 40)[0]
    if header != 4:
        raise ValueError('Expected v4 boot/init_boot header')
    packed = struct.unpack_from('<I', data, 16)[0]
    return dict(header_version=header, os_version_patch_packed=packed)


def collect(extract, avbtool, actual_source_spl):
    extract = Path(extract)
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(actual_source_spl)):
        raise ValueError('Actual frozen source SPL must be known')
    images = {}
    for name in IMAGES:
        path = extract/'img'/(name+'.img')
        with path.open('rb') as f:
            magic = f.read(4)
            f.seek(-64, 2)
            footer = f.read(4)
        # Partitions without their own vbmeta are verified through parent descriptors.
        if magic == b'AVB0' or footer == b'AVBf':
            text = subprocess.check_output(['python3', str(avbtool), 'info_image', '--image', str(path)], text=True)
            images[name] = parse_avb(text)
        else:
            images[name] = {'own_vbmeta': False}
    if any(images[n].get('own_vbmeta') is False for n in ('vbmeta', 'vbmeta_system', 'vbmeta_vendor', 'boot')):
        raise ValueError('Required signed image metadata absent')
    props = {}
    for name, rel in PROPS.items():
        found = []
        for line in (extract/'fs'/rel).read_text().splitlines():
            k, sep, v = line.partition('=')
            if sep and k.endswith(('.security_patch', '.os_patch_level')):
                found.append((k,v))
        if len(dict(found)) != len(found):
            raise ValueError('Duplicate emitted security property: '+name)
        props[name] = dict(found)
    if 'ro.build.version.security_patch' not in props['system'] or 'ro.vendor.build.security_patch' not in props['vendor']:
        raise ValueError('Required reported platform/vendor SPL absent')
    return dict(schema=1, actual_source_spl=actual_source_spl, avb=images, reported=props,
                boot_headers={name:boot_header(extract/'img'/(name+'.img')) for name in ('boot','init_boot')})


def compare(baseline, candidate):
    if baseline != candidate:
        differences = [k for k in sorted(set(baseline)|set(candidate)) if baseline.get(k) != candidate.get(k)]
        raise ValueError('Rollback/security equality FAILED: '+', '.join(differences))
    return {'pass': True, 'fields': ['avb', 'boot_headers', 'actual_source_spl', 'reported']}
