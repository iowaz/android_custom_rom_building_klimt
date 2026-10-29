#!/bin/bash
: "${EVOX_EXTRACT:?attempt extraction path required}"
: "${EVOX_TMP:?attempt temporary path required}"
# evox20 checks: evox14 coverage plus the device-metadata consistency pass (notes/evox20-implementation-plan.md).
F=${EVOX_EXTRACT}/fs
SP=$F/system/system/build.prop
PP=$F/product/etc/build.prop
# The build.props gen_build_prop.py writes; Make writes vendor/build.prop, which ALLBP adds.
IDBP="$SP $F/system_ext/etc/build.prop $F/product/etc/build.prop $F/odm/etc/build.prop $F/vendor_dlkm/etc/build.prop $F/odm_dlkm/etc/build.prop $F/system_dlkm/etc/build.prop"
ALLBP="$IDBP $F/vendor/build.prop"
INIT=$F/system/system/bin/init
CANARY='google/bluejay_beta/bluejay:CANARY/ZP11.260918.007/16484274:user/release-keys'
DESC='bluejay_beta-user CANARY ZP11.260918.007 16484274 release-keys'
BID=ZP11.260918.007; INC=16484274; FLAVOR=bluejay_beta-user
DISPLAY_ID='ZP11.260918.007 release-keys'
KERNEL_RELEASE='6.6.142-android15-8'; BUILDER=android-build
IDCHECKBP="$IDBP"
if [[ ${KLIMT_BUILD:-evox25} =~ ^evox([0-9]+)$ ]] && (( 10#${BASH_REMATCH[1]} >= 26 )); then
  CANARY='Xiaomi/klimt_global/klimt:17/OS3.3.260806.171839609/OS3.0.335.0.XOSMIXM:user/release-keys'
  BID=OS3.3.260806.171839609; INC=OS3.0.335.0.XOSMIXM; FLAVOR=klimt_global-user
  DISPLAY_ID=$BID
  DESC="klimt_global-user 17 $BID $INC release-keys"
  # The kernel release ends in -ab<build number> (evox26: ab26, evox27: ab27).
  KERNEL_RELEASE="6.6.142-android15-8-gf6a5b29f9fe5-ab$((10#${BASH_REMATCH[1]}))"; BUILDER=builder
  IDCHECKBP="$ALLBP"
fi
ok(){ if eval "$2" >/dev/null 2>&1; then echo "OK   $1"; else echo "FAIL $1"; fi; }
# absent <ERE> <files...>: every file exists and no line matches.
absent(){ local re=$1; shift; local f; for f in "$@"; do [ -f "$f" ] || return 1; done; ! grep -qE "$re" "$@"; }
# only <prop ERE> <value> <files...>: every file exists, some line sets a matching prop, and every such line has exactly <value>.
only(){ local re=$1 val=$2; shift 2; local f vals; for f in "$@"; do [ -f "$f" ] || return 1; done
  vals=$(grep -hE "^($re)=" "$@" | sed 's/^[^=]*=//'); [ -n "$vals" ] || return 1
  ! printf '%s\n' "$vals" | grep -qvxF -- "$val"; }
# each <prop ERE> <value> <files...>: only() for every file on its own, so every file must set the prop.
each(){ local re=$1 val=$2; shift 2; local f; for f in "$@"; do only "$re" "$val" "$f" || return 1; done; }
# no_rc_match <ERE>: no init .rc matches (system/etc/init must exist; other init dirs are searched when present).
no_rc_match(){ local d dirs=(); for d in $F/system/system/etc/init $F/system_ext/etc/init $F/product/etc/init $F/vendor/etc/init $F/odm/etc/init; do
  [ -d "$d" ] && dirs+=("$d"); done; [ -d $F/system/system/etc/init ] && ! grep -rqE "$1" "${dirs[@]}"; }
bash "$(dirname "$(realpath "$0")")/fixcheck14.sh"

echo '== evox20 build identity'
ok "every ro.build.display.id matches the selected build reference" "each 'ro\.build\.display\.id' '$DISPLAY_ID' $SP $PP"
ok "every ro.build.flavor matches the selected build reference" "each 'ro\.build\.flavor' '$FLAVOR' $SP $PP"
ok "every ro.build.description matches the selected build reference" "each 'ro\.build\.description' '$DESC' $SP $PP"
ok "every ro.build.version.security_patch is 2026-10-05" "each 'ro\.build\.version\.security_patch' 2026-10-05 $SP $PP"
ok "every partition build.id matches the selected build reference" "each 'ro\.([a-z_]+\.)?build\.id' '$BID' $IDCHECKBP"
ok "every partition build.version.incremental matches the selected build reference" "each 'ro\.([a-z_]+\.)?build\.version\.incremental' '$INC' $IDCHECKBP"
ok "every partition build.fingerprint matches the selected build reference" "each 'ro\.([a-z_]+\.)?build\.fingerprint' '$CANARY' $ALLBP"

echo '== evox20 product identity unchanged (decision D1)'
for kv in brand=Xiaomi device=klimt manufacturer=Xiaomi model=2506BPN68G; do
  ok "every partition product.${kv%%=*} is ${kv#*=}" "each 'ro\.product\.([a-z_]+\.)?${kv%%=*}' ${kv#*=} $ALLBP"
done
ok "every partition product.name is klimt, vendor klimt_global" "each 'ro\.product\.([a-z_]+\.)?name' klimt $IDBP && only 'ro\.product\.vendor\.name' klimt_global $F/vendor/build.prop"
ok "ro.product.board is klimt" "only 'ro\.product\.board' klimt $ALLBP"
ok "static attestation IDs unchanged (odm: klimt, Xiaomi)" "only 'ro\.product\.device_for_attestation' klimt $ALLBP && only 'ro\.product\.manufacturer_for_attestation' Xiaomi $ALLBP && absent '^ro\.product\.(brand|model|name)_for_attestation=' $ALLBP"
ok "odm and vendor marketname and cert unchanged" "each 'ro\.product\.([a-z_]+\.)?marketname' 'Xiaomi 15T Pro' $F/odm/etc/build.prop $F/vendor/build.prop && each 'ro\.product\.([a-z_]+\.)?cert' 2506BPN68G $F/odm/etc/build.prop $F/vendor/build.prop"
ok "init keeps the klimt attestation IDs" "strings $INIT | grep -qx klimt_global && strings $INIT | grep -qx 2506BPN68G"

echo '== evox20 no project-diagnostic properties'
ok "no ro.evolution* in any build.prop" "absent '^ro\.evolution' $ALLBP"
ok "no ro.lineage* in any build.prop" "absent '^ro\.lineage' $ALLBP"
ok "no persist.sys.evox* in any build.prop" "absent '^persist\.sys\.evox' $ALLBP"
ok "no init rc gives persist.sys.evox props a value" "no_rc_match 'setprop +persist\.sys\.evox[^ ]* +([^\" ]|\"[^\"])'"

echo '== evox20 kernel identity'
T=/mnt/wsl/build/compare/tools; export LD_LIBRARY_PATH=$T/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
B20=${EVOX_TMP}/evx20_boot; PV=${EVOX_TMP}/evx20-proc-version.txt
rm -rf $B20; $T/unpack_bootimg --boot_img ${EVOX_EXTRACT}/img/boot.img --out $B20 >/dev/null 2>&1
(lz4 -dc $B20/kernel 2>/dev/null || gzip -dc $B20/kernel 2>/dev/null || cat $B20/kernel 2>/dev/null) | strings | grep -m1 '^Linux version ' > $PV
sed 's/^/     /' $PV
HOST=$(sed -n 's/^ro\.build\.host=//p' $SP)
ok "kernel release matches the selected build reference" "grep -qF 'Linux version $KERNEL_RELEASE (' $PV"
ok "kernel builder and ROM build host match the selected reference" "[ -n '$HOST' ] && grep -qF '($BUILDER@$HOST) ' $PV"
ok "kernel build #1 with a UTC timestamp" "grep -qE ' #1 SMP PREEMPT .* UTC [0-9]{4}\$' $PV"
