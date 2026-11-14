from pathlib import Path
import json,os,sys,subprocess
B=Path('/mnt/d/android_rom_building');P=B/'repositories/android_custom_rom_building_klimt/build-setup/evox/pipeline'
BUILD='20261113.2';CONTROL='20261113'
os.environ['KLIMT_BUILD']=BUILD;sys.path.insert(0,str(P))
import controller,candidate_gates,rollback_security,kernel_carry
D=B/'diagnostics/builds'/BUILD;C=B/'diagnostics/builds'/CONTROL
manifest=B/'repositories/android_custom_rom_building_klimt/manifests/snapshots'/f'{CONTROL}.xml'
snapshot=D/f'{BUILD}-frozen.xml'
promoted=json.loads((C/'PROMOTED.json').read_text())
reports=Path(promoted['report']);results=reports/'RESULTS.json'
archive=Path(promoted['delivery'])/f'lineage_klimt-{CONTROL}-img.zip'
assert controller.sha(archive)==promoted['archive_sha256']
heads=lambda data:controller.expected_heads(controller.manifest_heads(data))
frozen=heads(snapshot.read_bytes())
verified=json.loads(results.read_text())
audit=kernel_carry.carry(verified['candidate_evidence']['kernel_audit'],
    candidate_gates.file_record(results),candidate_gates.file_record(manifest),
    candidate_gates.file_record(archive),frozen,heads)
dest=D/'kernel-audit-carried.json'
with dest.open('x') as stream:json.dump(audit,stream,indent=2);stream.write('\n')
extract=Path('/mnt/wsl/build/compare')/CONTROL/promoted['attempt']
inventory={row['path']:row for row in json.loads((reports/'image-files.json').read_text())}
for name in rollback_security.IMAGES:
    target=extract/'img'/(name+'.img'); row=inventory[target.name]
    assert controller.sha(target)==row['sha256'] and target.stat().st_size==row['bytes'],name
security=rollback_security.collect(extract,controller.S/'external/avb/avbtool.py','2026-11-01')
record=dict(schema=1,baseline_manifest_sha256=controller.sha(manifest),
    archive=candidate_gates.file_record(archive),verified_results=candidate_gates.file_record(results),
    image_inventory=candidate_gates.file_record(reports/'image-files.json'),security=security)
control=D/'control-security.json'
with control.open('x') as stream:json.dump(record,stream,indent=2);stream.write('\n')
subprocess.run(['python3','-B',str(P/'ready.py'),str(snapshot),'--mode','full',
    '--reason','Owner-requested keybox monitor revision across framework, system service, Settings and translations',
    '--kernel-audit',str(dest),'--rollback-baseline',str(control),
    '--gate','keybox implementation and review='+str(B/'diagnostics/features/keybox-monitor'/BUILD/'IMPLEMENTATION.json')],check=True)
