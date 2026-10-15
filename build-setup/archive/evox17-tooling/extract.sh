#!/bin/bash
set -euo pipefail
Z=$1
E=$2
T=/mnt/wsl/build/compare/tools
test ! -e "$E"
mkdir -p "$E/img" "$E/fs" "$E/tmp"
export LD_LIBRARY_PATH="$T/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
unzip -q "$Z" -d "$E/img"
(cd "$E/img"; sha256sum *.img > ../archive-images.sha256)
for p in system system_ext product vendor odm vendor_dlkm system_dlkm odm_dlkm; do
    f="$E/img/$p.img"
    test -f "$f"
    if file "$f" | grep -q 'Android sparse'; then
        "$T/simg2img" "$f" "$f.raw"
        mv "$f.raw" "$f"
    fi
    kind=$(file -b "$f")
    echo "evox $p: $kind"
    case "$kind" in
        EROFS*) fsck.erofs --extract="$E/fs/$p" "$f" > "$E/tmp/extract-$p.log" 2>&1 ;;
        *ext*) mkdir "$E/fs/$p"; debugfs -R "rdump / $E/fs/$p" "$f" > "$E/tmp/extract-$p.log" 2>&1 ;;
        *) echo "Unsupported filesystem for $p: $kind"; exit 2 ;;
    esac
    test -d "$E/fs/$p"
    test -n "$(find "$E/fs/$p" -mindepth 1 -print -quit)"
done
(cd "$E/img"; sha256sum *.img > ../img.sha256)
du -sh "$E/fs"
