#!/usr/bin/env python3
"""Prepare reviewed comparison copies without modifying the historical tooling.

This script only writes Evox17 tooling. It never extracts an image or runs checks.
"""
import hashlib,json,re
from pathlib import Path
B=Path(__file__).resolve().parent
OLD=B.parent
OUT=B/'legacy'
OUT.mkdir(exist_ok=True)
inputs={}

def port(name,text):
    text=text.replace('/mnt/c/XiaomiBuilds/build-setup/evox/cmp/', '/mnt/c/XiaomiBuilds/build-setup/evox/evox17/legacy/')
    text=text.replace('/mnt/wsl/build/compare/evox', '${EVOX_EXTRACT}')
    text=text.replace('/tmp/', '${EVOX_TMP}/')
    text=text.replace('rm -rf ${EVOX_TMP}/evx_vb;', 'test ! -e ${EVOX_TMP}/evx_vb;')
    text=text.replace('rm -rf ${EVOX_TMP}/evx_rd;', 'test ! -e ${EVOX_TMP}/evx_rd;')
    text=text.replace('rm -rf ${EVOX_TMP}/evx_boot;', 'test ! -e ${EVOX_TMP}/evx_boot;')
    text=text.replace('rm -rf ${EVOX_TMP}/ota7;', 'test ! -e ${EVOX_TMP}/ota7;')
    if name=='fixcheck.sh':
        lines=text.splitlines()
        lines=[('ok "USB HALs labelled mtk_hal_usb_exec" "grep -F \'usb-aidl-service\\\\.mediatekv1\\\\.0\' $F/vendor/etc/selinux/vendor_file_contexts | grep -q mtk_hal_usb_exec && grep -F \'usb\\\\.gadget-aidl-service\\\\.mediatekv1\\\\.0\' $F/vendor/etc/selinux/vendor_file_contexts | grep -q mtk_hal_usb_exec"')
               if l.startswith('ok "USB HALs') else l for l in lines]
        lines=[('ok "fingerprint HAL may use power HAL" "grep -E \'^\\(typeattributeset hal_power_client \' $CIL | grep -qw hal_fingerprint_default && grep -qE \'^\\(allow hal_power_client hal_power_(hwservice|service) \\(.*find\' $F/system/system/etc/selinux/plat_sepolicy.cil"')
               if l.startswith('ok "fingerprint HAL may use') else l for l in lines]
        # CIL variable was absent in this first-stage script.
        lines.insert(2,'CIL=$F/vendor/etc/selinux/vendor_sepolicy.cil')
        text='\n'.join(lines)+'\n'
    if name=='fixcheck9.sh':
        text=text.replace('git -C $W/${p%%:*} log -8 --format=%s | grep -qxF \\"${p#*:}\\"',
                          'python3 -B /mnt/c/XiaomiBuilds/build-setup/evox/evox17/source-gate.py \\"${p%%:*}\\" \\"${p#*:}\\"')
        for l in text.splitlines():
            if l.startswith('ok "runtime APEX rebuilt'):
                text=text.replace(l, 'ok "runtime APEX rebuilt after the libc" "python3 -B /mnt/c/XiaomiBuilds/build-setup/evox/evox17/producer-check.py runtime-apex"')
    if name=='fixcheck13.sh':
        text=text.replace("git -C /mnt/wsl/evox/src/frameworks/native log -3 --format=%s | grep -q 'SMPTE 2094-50'", "python3 -B /mnt/c/XiaomiBuilds/build-setup/evox/evox17/source-gate.py frameworks/native 'SMPTE 2094-50 capability guard'")
    if name=='musthold.sh':
        text=text.replace('E=$C/evox;', 'E=${EVOX_EXTRACT};')
    text=text.replace('/mnt/c/XiaomiBuilds/build-setup/evox/evox17/legacy/evox12-libui.sha256','/mnt/c/XiaomiBuilds/build-setup/evox/evox17/evox12-libui.sha256')
    pre=': "${EVOX_EXTRACT:?attempt extraction path required}"\n: "${EVOX_TMP:?attempt temporary path required}"\n'
    text=text.replace('#!/bin/bash\n','#!/bin/bash\n'+pre,1)
    return text

for name in ['musthold.sh','fixcheck.sh','fixcheck7.sh','fixcheck8.sh','fixcheck9.sh','fixcheck10.sh','fixcheck11.sh','fixcheck12.sh','fixcheck13.sh','fixcheck14.sh']:
    src=OLD/'cmp'/name
    data=src.read_bytes()
    inputs[str(src)]=hashlib.sha256(data).hexdigest()
    text=port(name,data.decode().replace('\r\n','\n'))
    dest=OUT/name
    if dest.exists() and dest.read_text()!=text:
        raise RuntimeError('Refusing to overwrite differing port: '+str(dest))
    dest.write_text(text,newline='\n')
src=OLD/'cmp/evox12-libui.sha256'
(B/src.name).write_bytes(src.read_bytes())
inputs[str(src)]=hashlib.sha256(src.read_bytes()).hexdigest()
# Keep the strict producer/hash/processed-VINTF checks developed for Evox15.
src=OLD/'fix15/check-image.py'
data=src.read_bytes();inputs[str(src)]=hashlib.sha256(data).hexdigest()
text=data.decode().replace('from pathlib import Path','from pathlib import Path\nimport os').replace("F=Path('/mnt/wsl/build/compare/evox/fs');RD=Path('/tmp/evx_rd')", "F=Path(os.environ['EVOX_EXTRACT'])/'fs';RD=Path(os.environ['EVOX_TMP'])/'evx_rd'").replace('evox15 ', 'retained HIS/Health ')
text=text.replace('assert len(checks)==10\n','')
dest=B/'check-health-his.py'
if dest.exists() and dest.read_text()!=text:
    raise RuntimeError('Refusing to overwrite differing Health/HIS port')
dest.write_text(text,newline='\n')
(B/'historical-inputs.json').write_text(json.dumps(inputs,indent=2,sort_keys=True)+'\n')
# Coverage is by exact check identity, not a minimum OK count or FAIL allowance.
log=Path('C:/XiaomiBuilds/compare/evox15/raw-fixcheck15.txt') if str(B).startswith('C:') else Path('/mnt/c/XiaomiBuilds/compare/evox15/raw-fixcheck15.txt')
names=[]
for l in log.read_text().splitlines():
    if l.startswith(('OK   ','FAIL ')):
        name=l[5:].strip().replace('evox15 ', 'retained HIS/Health ')
        name=re.sub(r'\([0-9a-f]{16}\)', '(certificate)',name)
        if name in names:
            raise RuntimeError('Historical duplicate check identity: '+name)
        names.append(name)
(B/'expected-legacy-checks.json').write_text(json.dumps(names,indent=2)+'\n')
print('Prepared attempt-parameterized legacy comparisons and exact coverage inventory:',len(names),'checks')
