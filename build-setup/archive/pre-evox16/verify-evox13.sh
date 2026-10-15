#!/bin/bash
# After evox13 (copy of verify-evox12.sh with fixcheck13): save the img zip to D:, unpack it, run must-hold + evox13 checks. Reports in C:\XiaomiBuilds\compare\<name>.
set -e
N=${1:-evox13}
P=/mnt/wsl/evox/src/out/target/product/klimt; D=/mnt/d/WitAquaBuild/out-evox; R=/mnt/c/XiaomiBuilds/compare/$N
Z=$D/lineage_klimt-$N-img.zip
mkdir -p $R
ls -la $P/lineage_klimt-img.zip
cp -f $P/lineage_klimt-img.zip $Z
( cd $D && sha256sum lineage_klimt-$N-img.zip >> SHA256SUMS && sort -u -k2 SHA256SUMS -o SHA256SUMS && sha256sum -c --ignore-missing SHA256SUMS )
rm -rf /mnt/wsl/build/compare/evox
bash /mnt/c/XiaomiBuilds/build-setup/evox/cmp/cmp-extract-evox.sh $Z > $R/raw-extract.txt 2>&1
set +e
bash /mnt/c/XiaomiBuilds/build-setup/evox/cmp/musthold.sh > $R/raw-musthold.txt 2>&1
bash /mnt/c/XiaomiBuilds/build-setup/evox/cmp/fixcheck13.sh > $R/raw-fixcheck13.txt 2>&1
echo "== musthold highlights"
grep -E "^exit=|IDENTICAL|DIFFERS|CRC MISMATCHES|Linux version|vermagic|Verifying|ERROR|rror" $R/raw-musthold.txt | head -30
echo "== fixcheck13"
grep -E "^(OK|FAIL)" $R/raw-fixcheck13.txt
