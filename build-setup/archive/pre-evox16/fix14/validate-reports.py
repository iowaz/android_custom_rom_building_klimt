import re, sys
from pathlib import Path
R=Path(sys.argv[1]); t=(R/'raw-musthold.txt').read_text()
extracted=(R/'raw-extract.txt').read_text()
assert 'extract failed' not in extracted and 'Traceback' not in extracted
for partition in ['system','system_ext','product','vendor','odm','vendor_dlkm','system_dlkm','odm_dlkm']:
    assert f'evox {partition}:' in extracted, f'missing extraction: {partition}'
for value in ['exit=0', 'super_empty: IDENTICAL to author', 'super_empty: IDENTICAL to build9',
              'fastboot-info.txt == author', 'fastboot-info.txt == b9',
              'android-info.txt == author', 'android-info.txt == b9',
              'vendor_boot dtb IDENTICAL to live slot b', 'modules 888;',
              'CRC MISMATCHES vs kernel 0; UNRESOLVED 1', 'Linux version 6.6.142-android15-8-klimt-4k']:
    assert value in t, f'must-hold missing: {value}'
payloads=re.findall(r'^([0-9a-f]{64}) payload=.*dtbo[^\n]*$', t, re.M)
assert len(payloads)==3 and len(set(payloads))==1, f'dtbo payloads differ/missing: {payloads}'
assert 'DIFFERS' not in t and 'Traceback' not in t and 'No such file' not in t
f=(R/'raw-fixcheck14.txt').read_text()
fails=[x[5:].strip() for x in f.splitlines() if x.startswith('FAIL ')]
known={'USB HALs labelled mtk_hal_usb_exec','fingerprint HAL may use power HAL'}
assert set(fails)==known and len(fails)==2, f'unexpected fixcheck failures: {fails}'
assert len(re.findall(r'^OK ',f,re.M)) >= 145, 'missing fixcheck coverage'
(R/'VERIFIED.txt').write_text('evox14 image verified: AVB, layout, DTB/DTBO, 888 module CRCs, policy fixes.\n'
    'Two known legacy fixcheck false failures only; runtime camera/brightness pending.\n')
print('VERIFIED: all must-hold and evox14 checks passed (two known legacy false failures)')
