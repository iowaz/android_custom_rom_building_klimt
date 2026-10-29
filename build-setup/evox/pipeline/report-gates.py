#!/usr/bin/env python3
"""Strict historical comparison identities; no count threshold or FAIL waiver."""
import json,re
from pathlib import Path
B=Path(__file__).resolve().parent
def validate(report,build):
    if not re.fullmatch(r'evox[0-9]+',build):raise ValueError('Invalid build profile')
    text=(report/'raw-musthold.txt').read_text()
    extracted=(report/'raw-extract.txt').read_text()
    if any(x in extracted for x in ['extract failed','Traceback','Unsupported filesystem']):
        raise ValueError('Extraction tool failure')
    for p in ['system','system_ext','product','vendor','odm','vendor_dlkm','system_dlkm','odm_dlkm']:
        if f'evox {p}:' not in extracted:raise ValueError('Missing filesystem: '+p)
    required=['exit=0','super_empty: IDENTICAL to author','super_empty: IDENTICAL to build9',
        'fastboot-info.txt == author','fastboot-info.txt == b9','android-info.txt == author','android-info.txt == b9',
        'vendor_boot dtb IDENTICAL to live slot b','modules 888;',
        'CRC MISMATCHES vs kernel 0; UNRESOLVED 1','  unresolved mtk_drm_gateic_set_backlight']
    number=int(build.removeprefix('evox'))
    if number >= 26:
        # The kernel release ends in -ab<build number> (evox26: ab26, evox27: ab27).
        kernel=re.findall(r'^Linux version .*$',text,re.M)
        if len(kernel)!=1 or not kernel[0].startswith(f'Linux version 6.6.142-android15-8-gf6a5b29f9fe5-ab{number} (builder@pangu-build-component-system-247-r6kfm) ') or not kernel[0].endswith('#1 SMP PREEMPT Thu Aug 6 00:00:00 UTC 2026'):
            raise ValueError('Kernel identity differs from the selected build reference')
    else:
        required.append('Linux version 6.6.142-android15-8 (android-build@')
    for value in required:
        if value not in text:raise ValueError('Must-hold missing: '+value)
    if any(x in text for x in ['DIFFERS','Traceback','No such file','  MISMATCH']):
        raise ValueError('Must-hold failure/tool error')
    payloads=re.findall(r'^([0-9a-f]{64}) payload=.*dtbo[^\n]*$',text,re.M)
    if len(payloads)!=3 or len(set(payloads))!=1:raise ValueError('DTBO payload disagreement/missing')
    fix=(report/'raw-fixcheck.txt').read_text()
    if 'Traceback' in fix:raise ValueError('Patch checker execution error')
    records=[]
    for line in fix.splitlines():
        if line.startswith(('OK   ','FAIL ')):
            records.append((re.sub(r'\([0-9a-f]{16}\)','(certificate)',line[5:].strip()),line.startswith('OK   ')))
    names=[name for name,passed in records]
    expected=json.loads((B/'expected-legacy-checks.json').read_text())
    if len(set(names))!=len(names):raise ValueError('Duplicate patch check identity')
    if set(names)!=set(expected):raise ValueError('Coverage identity mismatch: missing='+str(sorted(set(expected)-set(names)))+' extra='+str(sorted(set(names)-set(expected))))
    failed=[name for name,passed in records if not passed]
    if failed:raise ValueError('Patch packaging failures: '+str(failed))
    return {'musthold':'pass','profile':build,'checks':[{'name':n,'pass':p} for n,p in records],
            'historical_module_count':888,'unresolved_symbol':'mtk_drm_gateic_set_backlight'}
if __name__=='__main__':
    import sys
    import paths
    print(json.dumps(validate(Path(sys.argv[1]),paths.current_build()),indent=2))
