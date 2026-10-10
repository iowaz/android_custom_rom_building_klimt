#!/bin/bash
# Generate Evo private keys once (never overwrite) and back them up to D:\XiaomiBuilds\keys. Never prints key material.
set -e
K=/mnt/wsl/evox/src/vendor/evolution-priv/keys
B=/mnt/d/XiaomiBuilds/keys
cd $K
if ls *.pk8 2>/dev/null | grep -qv '^releasekey.pk8$\|^testkey.pk8$' || [ -f avb.pk8 ]; then
  echo "keys already exist, not regenerating"
else
  # testkey.pk8 is generated too; releasekey.* are template symlinks to testkey.*
  ./keys.sh > /mnt/wsl/evox/logs/keys-generate.log 2>&1
fi
echo "pk8: $(ls *.pk8 | wc -l)  x509: $(ls *.x509.pem | wc -l)  avb: $(ls avb.pk8 avb_custom_key.bin 2>/dev/null | tr '\n' ' ')"
echo "Android.bp certificates: $(grep -c android_app_certificate Android.bp)"
# Sanity: platform/testkey certs are not the AOSP test certs
for k in testkey platform shared media networkstack; do
  a=$(openssl x509 -in $k.x509.pem -noout -fingerprint -sha256 | cut -d= -f2 | cut -c1-23)
  b=$(openssl x509 -in /mnt/wsl/evox/src/build/make/target/product/security/$k.x509.pem -noout -fingerprint -sha256 | cut -d= -f2 | cut -c1-23)
  [ "$a" != "$b" ] && echo "$k: new cert ($a...)" || echo "$k: SAME AS AOSP TEST KEY"
done
# Backup: one tarball (keys + generated Android.bp + keys.mk), private permissions
mkdir -p $B
ts=$(date +%Y%m%d-%H%M)
tar -C /mnt/wsl/evox/src/vendor/evolution-priv -czf $B/evox-priv-keys-$ts.tar.gz --exclude=keys/.git keys
( cd $B && sha256sum evox-priv-keys-$ts.tar.gz > evox-priv-keys-$ts.tar.gz.sha256 )
ls -la $B
tar -tzf $B/evox-priv-keys-$ts.tar.gz | wc -l
