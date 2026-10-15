#!/bin/bash
: "${EVOX_EXTRACT:?attempt extraction path required}"
: "${EVOX_TMP:?attempt temporary path required}"
# Must-hold checks for the Evo build (EVOX_BUILD_PROMPT.md "Verify the output")
C=/mnt/wsl/build/compare; T=$C/tools; W=/mnt/wsl/evox/src; E=${EVOX_EXTRACT}; A=$C/author; B=$C/b9
L=${KLIMT_ROOT:-/mnt/d/android_rom_building}/backups/PartitionsBackup; U=$C/live/unpack; O=$W/out/target/product/klimt
export LD_LIBRARY_PATH=$T/lib64; AVB="python3 $W/external/avb/avbtool.py"
sec(){ echo; echo "################ $*"; }
sec "M1. sha256 of the Evo images"; cat $E/img.sha256
sec "M2. avbtool verify_image --follow_chain_partitions (Evo)"
(cd $E/img && $AVB verify_image --image vbmeta.img --follow_chain_partitions 2>&1); echo "exit=$?"
sec "M3. super_empty vs author / build9"
cmp $A/img/super_empty.img $E/img/super_empty.img && echo "super_empty: IDENTICAL to author"
cmp $B/img/super_empty.img $E/img/super_empty.img && echo "super_empty: IDENTICAL to build9"
$T/lpdump $E/img/super_empty.img 2>&1 | grep -iE "size|Name:|Group|slot" | head -30
grep -h "BOARD_SUPER_PARTITION_SIZE\|BOARD_.*_PARTITION_LIST\|BOARD_.*GROUP.*SIZE" $W/device/xiaomi/klimt/BoardConfig.mk
sec "M4. fastboot-info.txt / android-info.txt vs author and build9"
for f in fastboot-info.txt android-info.txt; do for s in author b9; do cmp -s $C/$s/img/$f $E/img/$f && echo "$f == $s" || { echo "$f DIFFERS from $s:"; diff $C/$s/img/$f $E/img/$f; }; done; done
sec "M5. dtbo / vendor_boot dtb vs live slot b (PartitionsBackup)"
for f in $L/dtbo_b.img $E/img/dtbo.img $B/img/dtbo.img; do n=$($AVB info_image --image $f | awk '/Image Size/{print $3}'); echo "$(head -c $n $f | sha256sum | cut -c1-64) payload=$n file=$(stat -c %s $f) $f"; done
cmp $L/dtbo_b.img $E/img/dtbo.img && echo "dtbo.img whole-file IDENTICAL to dtbo_b.img" || echo "(dtbo whole file differs: AVB footer/signature region; payload compared above)"
test ! -e ${EVOX_TMP}/evx_vb; $T/unpack_bootimg --boot_img $E/img/vendor_boot.img --out ${EVOX_TMP}/evx_vb > ${EVOX_TMP}/evx_vb.txt 2>&1
sha256sum $U/XiaomiBuilds_vendor_boot_b/dtb ${EVOX_TMP}/evx_vb/dtb $U/b9_vendor_boot/dtb 2>&1
cmp $U/XiaomiBuilds_vendor_boot_b/dtb ${EVOX_TMP}/evx_vb/dtb && echo "vendor_boot dtb IDENTICAL to live slot b"
sec "M6. Module CRCs vs Evo Module.symvers (vendor_dlkm + vendor_boot ramdisk + system_dlkm)"
SYM=$O/obj/KERNEL_OBJ/Module.symvers; echo "Module.symvers: $(wc -l < $SYM) symbols"
test ! -e ${EVOX_TMP}/evx_rd; mkdir -p ${EVOX_TMP}/evx_rd; for r in ${EVOX_TMP}/evx_vb/vendor_ramdisk*; do n=$(basename $r); mkdir -p ${EVOX_TMP}/evx_rd/$n; (lz4 -dc $r 2>/dev/null || gzip -dc $r) > ${EVOX_TMP}/evx_rd/$n.cpio; python3 /mnt/c/XiaomiBuilds/build-setup/cpio_extract.py ${EVOX_TMP}/evx_rd/$n.cpio ${EVOX_TMP}/evx_rd/$n >/dev/null; done
python3 - $SYM $E/fs/vendor_dlkm/lib/modules ${EVOX_TMP}/evx_rd $E/fs/system_dlkm <<'PY'
import sys,os,struct,subprocess
symvers={}
for l in open(sys.argv[1]):
    p=l.split('\t')
    if len(p)>1: symvers[p[1]]=int(p[0],16)
def secs(d):
    shoff=struct.unpack_from('<Q',d,0x28)[0]; es,n,si=struct.unpack_from('<HHH',d,0x3a)
    S=[struct.unpack_from('<IIQQQQ',d,shoff+i*es) for i in range(n)]
    so=S[si][4]; name=lambda x:d[so+x:d.index(b'\0',so+x)].decode()
    return {name(s[0]):(s[4],s[5]) for s in S}
def versions(d,S):
    off,size=S.get('__versions',(0,0)); out={}
    for o in range(off,off+size,64): out[d[o+8:d.index(b'\0',o+8)].decode()]=struct.unpack_from('<Q',d,o)[0]&0xffffffff
    return out
def exports(path):
    r=subprocess.run(['nm','--defined-only',path],capture_output=True,text=True).stdout
    return {l.split()[-1][10:] for l in r.splitlines() if l.split() and l.split()[-1].startswith('__ksymtab_')}
mods=[os.path.join(dp,f) for root in sys.argv[2:] for dp,_,fs in os.walk(root) for f in fs if f.endswith('.ko')]
need={}; prov=set(); mism={}; nimp=0
for m in mods:
    d=open(m,'rb').read(); S=secs(d)
    for s,c in versions(d,S).items():
        if s=='module_layout': continue
        nimp+=1; need[s]=c
        if s in symvers and symvers[s]!=c: mism.setdefault(s,[]).append(os.path.basename(m))
    prov|=exports(m)
unres=sorted(set(need)-set(symvers)-prov)
print(f"modules {len(mods)}; versioned imports {nimp}; distinct symbols {len(need)}; CRC MISMATCHES vs kernel {len(mism)}; UNRESOLVED {len(unres)}")
for s,l in list(mism.items())[:20]: print("  MISMATCH",s,l[:4])
for s in unres[:20]: print("  unresolved",s)
PY
sec "M7. Kernel identity"
test ! -e ${EVOX_TMP}/evx_boot; $T/unpack_bootimg --boot_img $E/img/boot.img --out ${EVOX_TMP}/evx_boot >/dev/null 2>&1
(lz4 -dc ${EVOX_TMP}/evx_boot/kernel 2>/dev/null || gzip -dc ${EVOX_TMP}/evx_boot/kernel 2>/dev/null || cat ${EVOX_TMP}/evx_boot/kernel) | strings | grep -m1 "Linux version"
f=$(find $E/fs/vendor_dlkm -name '*.ko' | head -1); echo "vermagic $(basename $f): $(modinfo -F vermagic $f)"
