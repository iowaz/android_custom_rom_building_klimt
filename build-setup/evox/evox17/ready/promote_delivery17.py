"""Promote an image-checked evox17 attempt to the established flat locations (copied from the evox16 version).

No compiler, verifier, source edits, phone operations or file replacement.
"""
from pathlib import Path
import argparse,hashlib,json,os,re,shutil,zipfile

ROOT=Path('/mnt/c/Users/diogo/Documents/Codex/2026-10-14/ru')
FLAT=Path('/mnt/d/WitAquaBuild/out-evox')
COMPARE=Path('/mnt/c/XiaomiBuilds/compare/evox17')
OUTPUT=ROOT/'outputs'

def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for part in iter(lambda:f.read(4*1024*1024),b''):h.update(part)
 return h.hexdigest()

def copy_exclusive(source,dest):
 h=hashlib.sha256()
 with source.open('rb') as inp,dest.open('xb') as out:
  for part in iter(lambda:inp.read(4*1024*1024),b''):
   out.write(part);h.update(part)
 return h.hexdigest()

def main():
 p=argparse.ArgumentParser();p.add_argument('report');args=p.parse_args()
 report=Path(args.report).resolve();results=json.loads((report/'RESULTS.json').read_text())
 attempt=results['attempt'];assert re.fullmatch(r'evox17-attempt\d{2,}',attempt)
 assert (report/'VERIFIED.txt').is_file() and results['runtime_unvalidated'] is True
 assert results['historical']['musthold']=='pass'
 historic=results['historical']['checks']
 assert len(historic)==165 and len({v['name'] for v in historic})==165 and all(v['pass'] is True for v in historic)
 modes={'policy','patch_packaging','private_compatibility','health_semantics','gms_themes_apps','doze_packaging','install_integrity'}
 assert {v['coverage'] for v in results['supplemental']}==modes and all(v['exit']==0 for v in results['supplemental'])
 archive=Path(results['archive']).resolve();dest=archive.parent
 assert archive.name==f'lineage_klimt-{attempt}-img.zip' and dest.is_relative_to(FLAT.resolve()/'evox17')
 assert archive.stat().st_size==results['archive_bytes']
 # Check the complete verified attempt delivery before creating any flat file.
 for line in (dest/'SHA256SUMS').read_text().splitlines():
  digest,name=line.split('  ',1)
  assert Path(name).name==name and re.fullmatch('[0-9a-f]{64}',digest)
  assert sha(dest/name)==digest,(name,'verified delivery hash mismatch')
 assert sha(archive)==results['archive_sha256']
 assert (dest/'RESULTS.json').read_bytes()==(report/'RESULTS.json').read_bytes()
 assert (dest/'VERIFIED.txt').read_bytes()==(report/'VERIFIED.txt').read_bytes()
 oldstem=archive.name.removesuffix('-img.zip');stem='lineage_klimt-evox17'
 marker='VERIFIED-evox17.txt';canonical=FLAT/(stem+'-img.zip')
 names=[canonical.name,stem+'-flash.bat',stem+'-flash.sh',marker,'SHA256SUMS-evox17',
        'RESULTS-evox17.json','COMPARISON-evox17.md','SOURCE-evox17.xml','README-evox17.md']
 assert all(not (FLAT/n).exists() and not (OUTPUT/n).exists() for n in names),'Evox17 delivery already exists; preserve it'
 assert not (COMPARE/'FINAL_DELIVERY.json').exists()
 os.link(archive,canonical) # Same NTFS volume; preserves the verified attempt ZIP.
 for suffix in ['.bat','.sh']:
  source=dest/(oldstem+'-flash'+suffix)
  text=source.read_text().replace(archive.name,canonical.name).replace('VERIFIED.txt',marker)
  assert results['archive_sha256'] in text and canonical.name in text and marker in text
  assert 'update --skip-reboot' in text and 'klimt' in text and archive.name not in text
  with (FLAT/(stem+'-flash'+suffix)).open('x',newline='\r\n' if suffix=='.bat' else '\n') as out:out.write(text)
 for source,name in [(report/'RESULTS.json','RESULTS-evox17.json'),(report/'COMPARISON-evox17.md','COMPARISON-evox17.md'),(dest/'postverify.xml','SOURCE-evox17.xml')]:
  copy_exclusive(source,FLAT/name)
 readme=f'''# Evox17 controlled test image

Static image checks passed for {attempt}, lineage_klimt-cp2a-user, GMS and the existing signing keys. **NOT boot-tested.** Keep lineage_klimt-evox15-img.zip ready to restore (slot b, no wipe) before flashing this.

The ZIP contains the same 19 fastboot entries as Evox15. The Windows and Linux flashing helpers check this archive's SHA256, the Klimt product and VERIFIED-evox17.txt. They require an explicit /flash or --flash argument and leave reboot to the operator.

ZIP SHA256: {results['archive_sha256']}
Reports: C:\\XiaomiBuilds\\compare\\evox17\\{attempt}
Attempt delivery: {dest}

All 165 historical comparison identities and seven supplemental image tracks passed, including install integrity (no stray or duplicate packages; TelecomShim only). See COMPARISON-evox17.md and RESULTS-evox17.json for the retained evidence. Source commits remain unpublished. AOD, fingerprint, camera, charging and app/profile behavior require the separate runtime test matrix.
'''
 with (FLAT/'README-evox17.md').open('x') as f:f.write(readme)
 # Marker and checksums are created after every canonical payload has succeeded.
 copy_exclusive(dest/'VERIFIED.txt',FLAT/marker)
 canonical_hashes={name:sha(FLAT/name) for name in names if name!='SHA256SUMS-evox17'}
 assert canonical_hashes[canonical.name]==results['archive_sha256']
 with (FLAT/'SHA256SUMS-evox17').open('x') as f:f.write(''.join(d+'  '+n+'\n' for n,d in sorted(canonical_hashes.items())))
 for name in names:
  actual=copy_exclusive(FLAT/name,OUTPUT/name)
  assert actual==sha(FLAT/name),(name,'output copy mismatch')
  assert sha(OUTPUT/name)==actual,(name,'saved output mismatch')
 # Portable actual verification evidence, independent of the earlier source ZIP.
 packet=OUTPUT/'evox17-image-verification.zip';assert not packet.exists()
 with zipfile.ZipFile(packet,'x',compression=zipfile.ZIP_DEFLATED) as z:
  for path in sorted(report.rglob('*')):
   if path.is_file():z.write(path,'reports/'+str(path.relative_to(report)))
  for name in ['BUILD_READY.json','tooling-snapshot.json','owner.json','build-exit.json','watchdog-terminal.json','prebuild.xml','postbuild.xml']:
   source=Path('/mnt/wsl/evox/logs/evox17')/attempt/name
   assert source.is_file();z.write(source,'attempt/'+name)
  z.write(Path('/mnt/c/XiaomiBuilds/build-setup/evox/evox17/image-checks/check_image.py'),'supplemental/check_image.py')
  z.write(Path('/mnt/c/XiaomiBuilds/build-setup/evox/evox17/image-checks/references.json'),'supplemental/references.json')
 with packet.open('rb') as f:
  with zipfile.ZipFile(f) as z:assert z.testzip() is None
 with packet.with_suffix('.zip.sha256').open('x') as f:f.write(sha(packet)+'  '+packet.name+'\n')
 receipt={'attempt':attempt,'report':str(report),'archive_sha256':results['archive_sha256'],
          'canonical_directory':str(FLAT),'output_directory':str(OUTPUT),
          'canonical_sha256':canonical_hashes,'runtime_unvalidated':True,
          'verification_packet_sha256':sha(packet),'source_heads':results['source_heads']}
 with (COMPARE/'FINAL_DELIVERY.json').open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
 copy_exclusive(COMPARE/'FINAL_DELIVERY.json',OUTPUT/'EVOX17_FINAL_DELIVERY.json')
 print('Verified attempt promoted:',canonical,flush=True)

if __name__=='__main__':main()
