#!/bin/bash
: "${EVOX_EXTRACT:?attempt extraction path required}"
: "${EVOX_TMP:?attempt temporary path required}"
# evox20 checks: evox14 coverage plus the device-metadata consistency pass (notes/evox20-implementation-plan.md).
F=${EVOX_EXTRACT}/fs
SP=$F/system/system/build.prop
# The build.props gen_build_prop.py writes; Make writes vendor/build.prop, which ALLBP adds.
IDBP="$SP $F/system_ext/etc/build.prop $F/product/etc/build.prop $F/odm/etc/build.prop $F/vendor_dlkm/etc/build.prop $F/odm_dlkm/etc/build.prop $F/system_dlkm/etc/build.prop"
ALLBP="$IDBP $F/vendor/build.prop"
INIT=$F/system/system/bin/init
CANARY='google/bluejay_beta/bluejay:CANARY/ZP11.260918.007/16484274:user/release-keys'
DESC='bluejay_beta-user CANARY ZP11.260918.007 16484274 release-keys'
ok(){ if eval "$2" >/dev/null 2>&1; then echo "OK   $1"; else echo "FAIL $1"; fi; }
# absent <ERE> <files...>: every file exists and no line matches.
absent(){ local re=$1; shift; local f; for f in "$@"; do [ -f "$f" ] || return 1; done; ! grep -qE "$re" "$@"; }
# only <prop ERE> <value> <files...>: every file exists, some line sets a matching prop, and every such line has exactly <value>.
only(){ local re=$1 val=$2; shift 2; local f vals; for f in "$@"; do [ -f "$f" ] || return 1; done
  vals=$(grep -hE "^($re)=" "$@" | sed 's/^[^=]*=//'); [ -n "$vals" ] || return 1
  ! printf '%s\n' "$vals" | grep -qvxF -- "$val"; }
# no_rc_match <ERE>: no init .rc matches (system/etc/init must exist; other init dirs are searched when present).
no_rc_match(){ local d dirs=(); for d in $F/system/system/etc/init $F/system_ext/etc/init $F/product/etc/init $F/vendor/etc/init $F/odm/etc/init; do
  [ -d "$d" ] && dirs+=("$d"); done; [ -d $F/system/system/etc/init ] && ! grep -rqE "$1" "${dirs[@]}"; }
bash "$(dirname "$(realpath "$0")")/fixcheck14.sh"

echo '== evox20 build identity'
ok "every ro.build.display.id is ZP11.260918.007 release-keys" "only 'ro\.build\.display\.id' 'ZP11.260918.007 release-keys' $IDBP"
ok "every ro.build.flavor is bluejay_beta-user" "only 'ro\.build\.flavor' bluejay_beta-user $IDBP"
ok "every ro.build.description is the canary description" "only 'ro\.build\.description' '$DESC' $IDBP"
ok "every ro.build.version.security_patch is 2026-10-05" "only 'ro\.build\.version\.security_patch' 2026-10-05 $IDBP"
ok "every partition build.id is ZP11.260918.007" "only 'ro\.([a-z_]+\.)?build\.id' ZP11.260918.007 $IDBP"
ok "every partition build.version.incremental is 16484274" "only 'ro\.([a-z_]+\.)?build\.version\.incremental' 16484274 $IDBP"
ok "every partition build.fingerprint is the canary print" "only 'ro\.([a-z_]+\.)?build\.fingerprint' '$CANARY' $ALLBP"

echo '== evox20 product identity unchanged (decision D1)'
for kv in brand=Xiaomi device=klimt manufacturer=Xiaomi model=2506BPN68G; do
  ok "every partition product.${kv%%=*} is ${kv#*=}" "only 'ro\.product\.([a-z_]+\.)?${kv%%=*}' ${kv#*=} $ALLBP"
done
ok "init keeps the klimt attestation IDs" "strings $INIT | grep -qx klimt_global && strings $INIT | grep -qx 2506BPN68G"

echo '== evox20 no project-diagnostic properties'
ok "no ro.evolution* in any build.prop" "absent '^ro\.evolution' $ALLBP"
ok "no ro.lineage* in any build.prop" "absent '^ro\.lineage' $ALLBP"
ok "no persist.sys.evox* in any build.prop" "absent '^persist\.sys\.evox' $ALLBP"
ok "no init rc gives persist.sys.evox props a value" "no_rc_match 'setprop +persist\.sys\.evox[^ ]* +[^\" ]'"

echo '== evox20 kernel identity'
T=/mnt/wsl/build/compare/tools; export LD_LIBRARY_PATH=$T/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
B20=${EVOX_TMP}/evx20_boot; PV=${EVOX_TMP}/evx20-proc-version.txt
test -e $B20 || $T/unpack_bootimg --boot_img ${EVOX_EXTRACT}/img/boot.img --out $B20 >/dev/null 2>&1
(lz4 -dc $B20/kernel 2>/dev/null || gzip -dc $B20/kernel 2>/dev/null || cat $B20/kernel) | strings | grep -m1 '^Linux version ' > $PV
sed 's/^/     /' $PV
HOST=$(sed -n 's/^ro\.build\.host=//p' $SP)
ok "kernel release 6.6.142-android15-8 (no local suffix)" "grep -q '^Linux version 6\.6\.142-android15-8 (' $PV"
ok "kernel builder android-build@ROM build host" "[ -n '$HOST' ] && grep -qF '(android-build@$HOST) ' $PV"
ok "kernel build #1 with a UTC timestamp" "grep -qE ' #1 SMP PREEMPT .* UTC [0-9]{4}\$' $PV"
