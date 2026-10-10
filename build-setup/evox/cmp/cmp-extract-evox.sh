#!/bin/bash
# Unpack the Evo fastboot image zip and its filesystem images into /mnt/wsl/build/compare/evox (same layout as compare/b9)
set -e
C=/mnt/wsl/build/compare; T=$C/tools; Z=${1:-$(ls /mnt/d/WitAquaBuild/out-evox/*-img.zip | head -1)}
export LD_LIBRARY_PATH=$T/lib64
d=$C/evox; mkdir -p $d/img $d/fs
[ -f $d/img/system.img ] || unzip -q -o $Z -d $d/img
(cd $d/img && sha256sum *.img > ../img.sha256)
for p in system system_ext product vendor odm vendor_dlkm system_dlkm odm_dlkm; do
  f=$d/img/$p.img; [ -f $f ] || continue
  if file $f | grep -q "Android sparse"; then $T/simg2img $f $f.raw && mv $f.raw $f; fi
  t=$(file -b $f | cut -c1-30); echo "evox $p: $t"
  [ -d $d/fs/$p ] && continue
  case "$t" in EROFS*) fsck.erofs --extract=$d/fs/$p $f >/dev/null 2>&1 || echo "  erofs extract failed";;
    *ext*) mkdir -p $d/fs/$p && debugfs -R "rdump / $d/fs/$p" $f >/dev/null 2>&1 || echo "  ext4 extract failed";; esac
done
du -sh $d/fs
