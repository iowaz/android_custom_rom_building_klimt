#!/usr/bin/env python3
"""Fail evox26 delivery on incomplete Xiaomi metadata migration. Static image checks only."""
import json, os, re, sys
from pathlib import Path
FP='Xiaomi/klimt_global/klimt:17/OS3.3.260806.171839609/OS3.0.335.0.XOSMIXM:user/release-keys'
BID='OS3.3.260806.171839609'; INC='OS3.0.335.0.XOSMIXM'
HOST='pangu-build-component-system-247-r6kfm'
KNOWN='Base,Base11,Cupcake,Donut,Eclair,Eclair01,EclairMr1,Froyo,Gingerbread,GingerbreadMr1,Honeycomb,HoneycombMr2,IceCreamSandwich,IceCreamSandwichMr1,JellyBean,JellyBeanMr1,JellyBeanMr2,Kitkat,KitkatWatch,Lollipop,LollipopMr1,M,N,NMr1,O,OMr1,P,Q,R,S,Sv2,Tiramisu,UpsideDownCake,VanillaIceCream,Baklava,CinnamonBun'
PARTS={'system':'system/system/build.prop','system_ext':'system_ext/etc/build.prop','product':'product/etc/build.prop','odm':'odm/etc/build.prop','odm_dlkm':'odm_dlkm/etc/build.prop','system_dlkm':'system_dlkm/etc/build.prop','vendor_dlkm':'vendor_dlkm/etc/build.prop','vendor':'vendor/build.prop'}
def read_props(path):
    result={}
    for line in path.read_text().splitlines():
        if not line or line.startswith('#') or '=' not in line:continue
        key,val=line.split('=',1)
        if key in result and result[key]!=val:raise ValueError('conflicting property '+key)
        result[key]=val
    return result

def validate(fs,kernel):
    count=0
    build_epoch=read_props(fs/PARTS["system"])["ro.build.date.utc"]
    if not build_epoch.isdigit() or int(build_epoch)<1785974400:raise ValueError("platform date predates the requested kernel reference date")
    def require(props,key,want):
        nonlocal count
        if props.get(key)!=want:raise ValueError(f'{key}: expected {want!r}, got {props.get(key)!r}')
        count+=1
    for part,rel in PARTS.items():
        p=read_props(fs/rel)
        for tail,want in {'fingerprint':FP,'id':BID,'version.incremental':INC,'date.utc':build_epoch,'type':'user','tags':'release-keys'}.items():require(p,f'ro.{part}.build.{tail}',want)
        for tail,want in {'brand':'Xiaomi','device':'klimt','manufacturer':'Xiaomi','model':'2506BPN68G'}.items():require(p,f'ro.product.{part}.{tail}',want)
        if part in ('system','product'):
            for key,want in {'ro.build.fingerprint':FP,'ro.build.id':BID,'ro.build.display.id':BID,'ro.build.version.incremental':INC,'ro.build.flavor':'klimt_global-user','ro.build.description':f'klimt_global-user 17 {BID} {INC} release-keys','ro.build.user':'builder','ro.build.host':HOST,'ro.build.date.utc':build_epoch,'ro.build.version.known_codenames':KNOWN,'ro.build.version.security_patch':'2026-10-05','ro.build.version.codename':'REL','ro.build.version.all_codenames':'REL','ro.build.version.release':'17'}.items():require(p,key,want)
        if part=='system':require(p,'ro.bootimage.fingerprint',FP)
        if part=='vendor':require(p,'ro.vendor.build.security_patch','2026-10-05')
        for key,val in p.items():
            if re.fullmatch(r'ro\.(?:[a-z_]+\.)?build\.(?:fingerprint|id|flavor|description|host|user|version\.incremental|version\.known_codenames)',key) and any(x in val for x in ['bluejay','ZP11.260918.007','16484274','CANARY','r-06b84ad74750c689-xc7u']):raise ValueError('legacy metadata '+key)
    if not kernel.startswith('Linux version 6.6.142-android15-8-gf6a5b29f9fe5-ab26 (builder@'+HOST+') '):raise ValueError('kernel release/builder mismatch')
    if not kernel.rstrip().endswith('#1 SMP PREEMPT Thu Aug 6 00:00:00 UTC 2026'):raise ValueError('kernel timestamp mismatch')
    return count+2

def main():
    extract=Path(os.environ['EVOX_EXTRACT']);report=Path(os.environ['EVOX_REPORT'])/'metadata26.json'
    try:
        count=validate(extract/'fs',(Path(os.environ['EVOX_TMP'])/'evx20-proc-version.txt').read_text())
        result={'pass':True,'assertions':count,'runtime_validated':False}
    except (OSError,ValueError,KeyError) as e:result={'pass':False,'error':str(e),'runtime_validated':False}
    report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));return 0 if result['pass'] else 1
if __name__=='__main__':sys.exit(main())
