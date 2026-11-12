"""The simple-mode checks: archive, AVB, flash layout, live DTB, identity props, staging, platform signer, and
the kernel extra. Each function takes explicit inputs and raises verification.Defect (artifact/assertion,
exit 1) or verification.Missing (tool/evidence, exit 2). The callers in verify.py own locks, records and delivery.

Sources: legacy/musthold.sh M2-M6 (AVB chain, super_empty/fastboot-info/android-info against the author and
build9 references, DTBO payload and vendor_boot DTB against the live slot b, module CRCs), check-metadata26.py
(identity props), image-checks/check_image.py install_integrity (staging half).
"""
import base64
import hashlib
import importlib.util
import json
import os
import re
import shutil
import struct
import subprocess
import zipfile
from pathlib import Path

import paths
from verification import Defect, Missing

B = paths.PIPELINE
ENTRIES = frozenset({'android-info.txt', 'fastboot-info.txt', 'boot.img', 'dtbo.img', 'init_boot.img', 'odm.img',
    'odm_dlkm.img', 'product.img', 'super_empty.img', 'system.img', 'system_dlkm.img', 'system_ext.img',
    'unsparse_super_empty.img', 'vbmeta.img', 'vbmeta_system.img', 'vbmeta_vendor.img', 'vendor.img',
    'vendor_boot.img', 'vendor_dlkm.img'})
PARTITIONS = ('system', 'system_ext', 'product', 'vendor', 'odm', 'vendor_dlkm', 'system_dlkm', 'odm_dlkm')
CHUNK = 8*1024*1024
SPARSE_MAGIC = b'\x3a\xff\x26\xed'
TELECOM_APK = re.compile(r'[^/]+/(?:[^/]+/)*priv-app/(Telecom|TelecomShim)/[^/]+\.apk')
MODULE_COUNT = 888
UNRESOLVED = ['mtk_drm_gateic_set_backlight']


def load_script(name, filename):
    spec = importlib.util.spec_from_file_location(name, filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def file_sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for part in iter(lambda: f.read(CHUNK), b''):
            h.update(part)
    return h.hexdigest()


def tool_env():
    lib = str(paths.TOOLS/'lib64')
    return dict(os.environ, LD_LIBRARY_PATH=lib + (':' + os.environ['LD_LIBRARY_PATH'] if os.environ.get('LD_LIBRARY_PATH') else ''))


def run(argv, check=None, cwd=None, defect=False):
    """Run a tool; a missing tool or a nonzero exit is Missing (or Defect when the exit is the finding)."""
    try:
        result = subprocess.run([str(a) for a in argv], cwd=cwd, env=tool_env(), capture_output=True)
    except OSError as e:
        raise Missing(f'{argv[0]}: {e}', check) from e
    if result.returncode:
        message = f'{Path(str(argv[0])).name} exit {result.returncode}: ' + result.stderr.decode(errors='replace')[-400:]
        raise (Defect if defect else Missing)(message, check)
    return result.stdout


def require_tools(names):
    """One consolidated list of missing tools, before any copy or extraction."""
    missing = []
    for name in names:
        p = Path(name)
        if p.is_absolute():
            if not p.is_file():
                missing.append(str(p))
        elif not shutil.which(name):
            missing.append(name)
    if missing:
        raise Missing('Tools unavailable: ' + ', '.join(missing))


# --- archive ---------------------------------------------------------------------------------------------

def copy_with_digest(source, partial, expected_sha256, check='archive.integrity'):
    """Copy the producing ZIP to the delivery's .partial while hashing it (one read). Bytes must be the producer's."""
    h = hashlib.sha256()
    with open(source, 'rb') as src, open(partial, 'xb') as out:
        for part in iter(lambda: src.read(CHUNK), b''):
            h.update(part)
            out.write(part)
    digest = h.hexdigest()
    if digest != expected_sha256:
        raise Defect(f'Archive {source} sha256 {digest} differs from the producing build-exit {expected_sha256}', check)
    return digest


def extract_members(zip_path, dest, check='archive.integrity'):
    """Exact 19-entry set, then one CRC-checked pass that writes every member and hashes it. Returns the inventory."""
    try:
        with zipfile.ZipFile(zip_path) as z:
            infos = z.infolist()
            names = [i.filename for i in infos]
            if len(names) != len(set(names)) or set(names) != ENTRIES:
                raise Defect('Fastboot artifact inventory differs: extra=' + str(sorted(set(names)-ENTRIES)) +
                             ' missing=' + str(sorted(ENTRIES-set(names))) + ' entries=' + str(len(names)), check)
            Path(dest).mkdir(parents=True, exist_ok=False)
            inventory = []
            for info in infos:
                h = hashlib.sha256()
                with z.open(info) as member, open(Path(dest)/info.filename, 'xb') as out:
                    for part in iter(lambda: member.read(CHUNK), b''):
                        h.update(part)
                        out.write(part)
                inventory.append(dict(name=info.filename, bytes=info.file_size, compressed=info.compress_size,
                                      crc=info.CRC, sha256=h.hexdigest()))
    except zipfile.BadZipFile as e:  # zipfile raises this on a CRC mismatch at the end of a member
        raise Defect('ZIP CRC/structure failed: ' + str(e), check) from e
    return inventory


# --- AVB -------------------------------------------------------------------------------------------------

def avb_chain(img_dir, avbtool, baseline_keys, check='avb.chain'):
    """musthold M2: verify_image follows every chain partition and recomputes hashes/hashtrees (sparse images
    are read directly). The vbmeta and chained public keys must equal the baseline build's."""
    out = run(['python3', avbtool, 'verify_image', '--image', 'vbmeta.img', '--follow_chain_partitions'],
              check, cwd=img_dir, defect=True)
    from verification import vbmeta_keys
    info = run(['python3', avbtool, 'info_image', '--image', Path(img_dir)/'vbmeta.img'], check).decode()
    try:
        keys = vbmeta_keys(info)
    except ValueError as e:
        raise Defect(str(e), check) from e
    if keys != baseline_keys:
        raise Defect(f'AVB public keys differ from the baseline build: {keys} != {baseline_keys}; '
                     'a key change is never routine (verify in full)', check)
    return dict(verify_output=out.decode(errors='replace').strip().splitlines()[-3:], public_keys_sha1=keys)


# --- flash layout and live DTB ----------------------------------------------------------------------------

def readonly_layout_matches(new, old):
    """musthold M3: same lpdump layout once Evolution X's readonly attribute (build/make 90d0063) reads as none."""
    attrs = sorted({l for l in new.splitlines() if re.match(r'^ *Attributes:', l)})
    return attrs == ['  Attributes: readonly'] and new.replace('Attributes: readonly', 'Attributes: none') == old


def flash_layout(img_dir, references, lpdump, check='flash.layout'):
    """super_empty identical to, or the same layout as, each reference; fastboot-info/android-info identical."""
    img_dir = Path(img_dir)
    result = {}
    for ref, ref_dir in references.items():
        ours, theirs = img_dir/'super_empty.img', Path(ref_dir)/'super_empty.img'
        if not theirs.is_file():
            raise Missing('Reference image missing: '+str(theirs), check)
        if ours.read_bytes() == theirs.read_bytes():
            result[f'super_empty vs {ref}'] = 'identical'
        else:
            new = run([lpdump, ours], check).decode(errors='replace')
            old = run([lpdump, theirs], check).decode(errors='replace')
            if not readonly_layout_matches(new, old):
                raise Defect('super_empty layout differs from '+ref, check)
            result[f'super_empty vs {ref}'] = 'same layout, every partition readonly'
        for name in ('fastboot-info.txt', 'android-info.txt'):
            other = Path(ref_dir)/name
            if not other.is_file():
                raise Missing('Reference file missing: '+str(other), check)
            if (img_dir/name).read_bytes() != other.read_bytes():
                raise Defect(f'{name} differs from {ref}', check)
            result[f'{name} vs {ref}'] = 'identical'
    return result


def avb_payload_sha(path, avbtool, check='dtb.live'):
    info = run(['python3', avbtool, 'info_image', '--image', path], check).decode(errors='replace')
    size = re.findall(r'^\s*Image Size:\s*(\d+) bytes', info, re.M)  # the hash descriptor's line, as musthold's awk reads it
    if len(size) != 1:
        raise Defect('No unique AVB Image Size: '+str(path), check)
    with open(path, 'rb') as f:
        data = f.read(int(size[0]))
    if len(data) != int(size[0]):
        raise Defect('AVB image shorter than its payload: '+str(path), check)
    return hashlib.sha256(data).hexdigest()


def dtb_live(img_dir, live_dtbo, ref_dtbo, live_dtb, avbtool, unpack_bootimg, tmp, check='dtb.live'):
    """musthold M5: the DTBO payload equals the live slot b and build9; the vendor_boot DTB equals the live slot b."""
    for p in (live_dtbo, ref_dtbo, live_dtb):
        if not Path(p).is_file():
            raise Missing('Live/reference file missing: '+str(p), check)
    payloads = {str(p): avb_payload_sha(p, avbtool, check) for p in (live_dtbo, Path(img_dir)/'dtbo.img', ref_dtbo)}
    if len(set(payloads.values())) != 1:
        raise Defect('DTBO payload disagreement: '+json.dumps(payloads), check)
    vb = Path(tmp)/'simple-vendor-boot'
    run([unpack_bootimg, '--boot_img', Path(img_dir)/'vendor_boot.img', '--out', vb], check)
    if not (vb/'dtb').is_file():
        raise Defect('vendor_boot has no DTB', check)
    if (vb/'dtb').read_bytes() != Path(live_dtb).read_bytes():
        raise Defect('vendor_boot DTB differs from the live slot b', check)
    return dict(dtbo_payload_sha256=next(iter(payloads.values())), vendor_boot_dtb_sha256=file_sha(vb/'dtb'))


# --- identity ---------------------------------------------------------------------------------------------

def decompress(data):
    for argv in (['lz4', '-dc'], ['gzip', '-dc']):
        try:
            result = subprocess.run(argv, input=data, capture_output=True)
        except OSError:
            continue
        if result.returncode == 0 and result.stdout:
            return result.stdout
    return data


def kernel_banner(kernel):
    """The first `Linux version ...` string, as `strings | grep -m1` reads it in musthold M7."""
    i = kernel.find(b'Linux version ')
    if i < 0:
        return None
    end = min([j for j in (kernel.find(b'\n', i), kernel.find(b'\0', i)) if j >= 0] or [len(kernel)])
    return kernel[i:end].decode('ascii', errors='replace')


def boot_banner(boot_img, unpack_bootimg, tmp, check='identity.metadata'):
    out = Path(tmp)/'simple-boot'
    run([unpack_bootimg, '--boot_img', boot_img, '--out', out], check)
    if not (out/'kernel').is_file():
        raise Defect('boot.img has no kernel', check)
    banner = kernel_banner(decompress((out/'kernel').read_bytes()))
    if not banner:
        raise Defect('No Linux version banner in the packaged kernel', check)
    return banner


def identity_metadata(props_root, banner, build, expectation, check='identity.metadata'):
    """check-metadata26.validate over the staged build.prop files and the packaged kernel banner."""
    metadata = load_script('check_metadata26', B/'check-metadata26.py')
    for rel in metadata.PARTS.values():
        if not (Path(props_root)/rel).is_file():
            raise Missing('Staged build.prop missing from packaging evidence: '+rel, check)
    try:
        count = metadata.validate(Path(props_root), banner, build, expectation)
    except (ValueError, KeyError) as e:
        raise Defect('Identity metadata: '+str(e), check) from e
    return dict(assertions=count, banner=banner, props='staged at packaging time')


# --- staging and signing ----------------------------------------------------------------------------------

def staging_clean(evidence, check='staging.clean'):
    """install_integrity, staging half: every staged path is a product install (kernel module trees excepted);
    exactly one Telecom app, the variant the release flag selects, and the product selects the same one."""
    checker = load_script('check_image_helpers', B/'image-checks/check_image.py')
    facts = json.loads((Path(evidence)/'facts.json').read_text())
    if facts.get('listing_mtime_ns', -1) < facts.get('started_ns', 1 << 62):
        raise Defect('Install list was not written by this attempt', check)
    installable = {x.removeprefix('out/target/product/klimt/') for x in (Path(evidence)/'installable_files.txt').read_text().split()}
    staged = (Path(evidence)/'staged-paths.txt').read_text().splitlines()
    other, kernel = checker.stray_staged(staged, installable)
    if other:
        raise Defect(f'{len(other)} staged files are not product installs: {other[:20]}', check)
    modules = len([k for k in kernel if k.endswith('.ko')])
    if modules < 600:
        raise Defect(f'Kernel module trees missing from staging ({modules} .ko)', check)
    mainline = facts.get('telecom_mainline')
    if mainline not in ('true', 'false'):
        raise Missing('RELEASE_TELECOM_MAINLINE_MODULE unavailable in packaging evidence', check)
    want = 'system/priv-app/TelecomShim/TelecomShim.apk' if mainline == 'true' else 'system/priv-app/Telecom/Telecom.apk'
    telecom = sorted(s for s in staged if TELECOM_APK.fullmatch(s))
    if telecom != [want]:
        raise Defect(f'Telecom app variants staged {telecom}, expected only {want} (mainline={mainline})', check)
    selected = facts.get('selected_telecom')
    if not isinstance(selected, list) or ('TelecomShim' in selected) != (mainline == 'true') or ('Telecom' in selected) != (mainline != 'true'):
        raise Defect(f'Product Telecom selection {selected} does not match mainline={mainline}', check)
    return dict(staged_files=len(staged), installable=len(installable), kernel_module_files=len(kernel),
                telecom=want, listing=facts.get('listing'))


def pem_der_sha256(pem_text):
    body = re.search(r'-----BEGIN CERTIFICATE-----(.*?)-----END CERTIFICATE-----', pem_text, re.S)
    if not body:
        raise Missing('No certificate in PEM')
    return hashlib.sha256(base64.b64decode(''.join(body[1].split()))).hexdigest()


def platform_signer(apksigner_output, apksigner_exit, platform_pem, check='signing.platform'):
    """The staged framework-res.apk verifies and has exactly one signer: the reviewed platform certificate."""
    if apksigner_exit != 0:
        raise Defect('apksigner did not verify the staged framework-res.apk', check)
    # `Signer #1 ...` (v1/v2), `V3.0 Signer: ...` (v3-only APKs such as this framework-res), `Signer (minSdk...)`.
    signers = re.findall(r'^((?:V[\d.]+ )?Signer(?: #\d+| \([^)]*\))?):? certificate SHA-256 digest:\s*([0-9a-f]{64})\s*$',
                         apksigner_output, re.M)
    expected = pem_der_sha256(platform_pem)
    if not signers or {d for _, d in signers} != {expected}:
        raise Defect(f'framework-res.apk signers {signers} differ from the platform certificate {expected}', check)
    return dict(platform_certificate_sha256=expected, source='staged framework-res.apk')


# --- filesystems and the kernel extra ---------------------------------------------------------------------

def unsparse(image, simg2img, check):
    with open(image, 'rb') as f:
        magic = f.read(4)
    if magic == SPARSE_MAGIC:
        run([simg2img, image, str(image)+'.raw'], check)
        os.replace(str(image)+'.raw', image)


def filesystem_kind(image):
    with open(image, 'rb') as f:
        f.seek(1024)
        block = f.read(64)
    if block[:4] == b'\xe2\xe1\xf5\xe0':
        return 'erofs'
    if block[56:58] == b'\x53\xef':
        return 'ext'
    return None


def extract_filesystems(img_dir, fs_dir, partitions, simg2img, log_dir, check):
    """extract.sh for the named partitions: unsparse in place, then fsck.erofs --extract or debugfs rdump."""
    Path(fs_dir).mkdir(parents=True, exist_ok=True)
    for part in partitions:
        image, dest = Path(img_dir)/(part+'.img'), Path(fs_dir)/part
        if dest.exists():
            continue
        unsparse(image, simg2img, check)
        kind = filesystem_kind(image)
        log = Path(log_dir)/f'extract-{part}.log'
        if kind == 'erofs':
            log.write_bytes(run(['fsck.erofs', '--extract='+str(dest), image], check))
        elif kind == 'ext':
            dest.mkdir()
            log.write_bytes(run(['debugfs', '-R', f'rdump / {dest}', image], check))
        else:
            raise Missing('Unsupported filesystem for '+part, check)
        if not dest.is_dir() or not any(dest.iterdir()):
            raise Missing('Empty extraction: '+part, check)


def unpack_vendor_ramdisks(vendor_boot, unpack_bootimg, tmp, check):
    """musthold M5/M6 layout: EVOX_TMP/evx_vb (unpacked vendor_boot) and EVOX_TMP/evx_rd/<ramdisk>/ (cpio trees)."""
    vb, rd = Path(tmp)/'evx_vb', Path(tmp)/'evx_rd'
    if rd.exists():
        return rd
    run([unpack_bootimg, '--boot_img', vendor_boot, '--out', vb], check)
    rd.mkdir(parents=True)
    ramdisks = sorted(vb.glob('vendor_ramdisk*'))
    if not ramdisks:
        raise Defect('vendor_boot has no vendor ramdisk', check)
    for r in ramdisks:
        cpio = rd/(r.name+'.cpio')
        cpio.write_bytes(decompress(r.read_bytes()))
        (rd/r.name).mkdir()
        run(['python3', paths.EVOX_SETUP/'tools/cpio_extract.py', cpio, rd/r.name], check)
    return rd


def elf_sections(d):
    shoff = struct.unpack_from('<Q', d, 0x28)[0]
    es, n, si = struct.unpack_from('<HHH', d, 0x3a)
    table = [struct.unpack_from('<IIQQQQ', d, shoff+i*es) for i in range(n)]
    so = table[si][4]
    def name(x):
        return d[so+x:d.index(b'\0', so+x)].decode()
    return {name(s[0]): (s[4], s[5]) for s in table}


def module_versions(d, sections):
    off, size = sections.get('__versions', (0, 0))
    out = {}
    for o in range(off, off+size, 64):
        out[d[o+8:d.index(b'\0', o+8)].decode()] = struct.unpack_from('<Q', d, o)[0] & 0xffffffff
    return out


def module_exports(path):
    text = run(['nm', '--defined-only', path], 'kernel.modules').decode(errors='replace')
    return {l.split()[-1][10:] for l in text.splitlines() if l.split() and l.split()[-1].startswith('__ksymtab_')}


def module_crcs(symvers_path, roots):
    """musthold M6: versioned imports of every packaged module against Module.symvers and module exports."""
    symvers = {}
    for line in Path(symvers_path).read_text().splitlines():
        p = line.split('\t')
        if len(p) > 1:
            symvers[p[1]] = int(p[0], 16)
    modules = sorted(str(Path(dp)/f) for root in roots for dp, _, files in os.walk(root) for f in files if f.endswith('.ko'))
    need, provided, mismatches, imports = {}, set(), {}, 0
    for m in modules:
        d = Path(m).read_bytes()
        for symbol, crc in module_versions(d, elf_sections(d)).items():
            imports += 1
            need[symbol] = crc
            if symbol in symvers and symvers[symbol] != crc:
                mismatches.setdefault(symbol, []).append(Path(m).name)
        provided |= module_exports(m)
    unresolved = sorted(set(need)-set(symvers)-provided)
    return dict(modules=len(modules), imports=imports, symbols=len(need), mismatches=mismatches, unresolved=unresolved,
                symvers=str(symvers_path), symvers_sha256=file_sha(symvers_path))


def kernel_modules(symvers_path, roots, check='kernel.modules'):
    if not Path(symvers_path).is_file():
        raise Missing('Module.symvers unavailable: '+str(symvers_path), check)
    result = module_crcs(symvers_path, roots)
    if result['modules'] != MODULE_COUNT or result['mismatches'] or result['unresolved'] != UNRESOLVED:
        raise Defect(f"Modules {result['modules']} (want {MODULE_COUNT}), CRC mismatches "
                     f"{sorted(result['mismatches'])[:20]}, unresolved {result['unresolved']} (want {UNRESOLVED})", check)
    return result
