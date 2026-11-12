#!/usr/bin/env python3
"""Packaging-time staging evidence for simple verification, captured once by build.sh after updatepackage.

usage: python3 -B staging_evidence.py <attempt-dir> [<product-out>] [<soong-variables>]
Run by build.sh's exit hook on exit 0, inside the controller's source lock, from /mnt/wsl/evox/src.
Writes <attempt>/staging-evidence/ and prints {relative path: sha256} for build-exit.json:
  installable_files.txt   this attempt's install list (guarded current/.previous, see check_image.install_listing)
  staged-paths.txt        every file/symlink under the eight staging partitions, paths only
  props/<PARTS layout>    the eight staged build.prop files, laid out as check-metadata26.py reads them
  framework-res.apksigner.txt  `apksigner verify --print-certs` of the staged framework-res.apk
  facts.json              list choice and mtime, attempt start, Telecom mainline flag and product selection
These describe staging, not the packed images; the report labels them so. A later build cannot supply them.
"""
import hashlib, json, shutil, subprocess, sys
from pathlib import Path

PARTS = ('system', 'system_ext', 'product', 'vendor', 'odm', 'vendor_dlkm', 'system_dlkm', 'odm_dlkm')
STAGED_PROPS = {'system/system/build.prop': 'system/build.prop', 'system_ext/etc/build.prop': 'system_ext/etc/build.prop',
                'product/etc/build.prop': 'product/etc/build.prop', 'odm/etc/build.prop': 'odm/etc/build.prop',
                'odm_dlkm/etc/build.prop': 'odm_dlkm/etc/build.prop', 'system_dlkm/etc/build.prop': 'system_dlkm/etc/build.prop',
                'vendor_dlkm/etc/build.prop': 'vendor_dlkm/etc/build.prop', 'vendor/build.prop': 'vendor/build.prop'}
APKSIGNER = ('out/host/linux-x86/bin/apksigner', 'prebuilts/sdk/tools/linux/bin/apksigner')


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for part in iter(lambda: f.read(4*1024*1024), b''):
            h.update(part)
    return h.hexdigest()


def product_packages(node):
    """ProductPackages from the namespaced ProductPackagesSet (check_image.Check.selected)."""
    if isinstance(node, dict):
        if isinstance(node.get('ProductPackages'), list):
            return node['ProductPackages']
        for value in node.values():
            found = product_packages(value)
            if found is not None:
                return found
    return None


def capture(attempt, product_out, variables, src=Path('.')):
    out = Path(attempt)/'staging-evidence'
    out.mkdir()
    started = json.loads((Path(attempt)/'owner.json').read_text())['started_ns']
    current = Path(product_out)/'.installable_files'
    listing = current if current.exists() else Path(product_out)/'.installable_files.previous'
    shutil.copyfile(listing, out/'installable_files.txt')
    staged = sorted(str(p.relative_to(product_out)) for part in PARTS if (Path(product_out)/part).is_dir()
                    for p in (Path(product_out)/part).rglob('*') if p.is_file() or p.is_symlink())
    (out/'staged-paths.txt').write_text(''.join(s+'\n' for s in staged))
    for rel, staged_rel in STAGED_PROPS.items():
        (out/'props'/rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(product_out)/staged_rel, out/'props'/rel)
    soong = json.loads(Path(variables).read_text())
    # Searched over the whole document, like check_image: Android 17 keeps it under
    # PartitionVarsForSoongMigrationOnlyDoNotUse/ProductPackagesSet/<namespace>/ProductPackages.
    selected = product_packages(soong) or []
    tool = next((Path(src)/t for t in APKSIGNER if (Path(src)/t).is_file()), None)
    if tool is None:
        raise SystemExit('apksigner unavailable')
    signer = subprocess.run([str(tool), 'verify', '--print-certs', str(Path(product_out)/'system/framework/framework-res.apk')],
                            capture_output=True, text=True)
    (out/'framework-res.apksigner.txt').write_text(signer.stdout + signer.stderr)
    facts = dict(listing=listing.name, listing_mtime_ns=listing.stat().st_mtime_ns, started_ns=started,
                 telecom_mainline=soong.get('VendorVars', {}).get('ANDROID', {}).get('release_telecom_mainline_module'),
                 selected_telecom=sorted(p for p in selected if p in ('Telecom', 'TelecomShim')),
                 apksigner=str(tool), apksigner_exit=signer.returncode, soong_variables_sha256=digest(variables))
    (out/'facts.json').write_text(json.dumps(facts, indent=2, sort_keys=True)+'\n')
    return {str(p.relative_to(out)): digest(p) for p in sorted(out.rglob('*')) if p.is_file()}


if __name__ == '__main__':
    args = sys.argv[1:]
    if not 1 <= len(args) <= 3:
        raise SystemExit(__doc__)
    product = args[1] if len(args) > 1 else 'out/target/product/klimt'
    variables = args[2] if len(args) > 2 else 'out/soong/soong.lineage_klimt.variables'
    print(json.dumps(capture(args[0], product, variables)))
