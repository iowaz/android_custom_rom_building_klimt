#!/bin/bash
# Only the precheck supervisor invokes this wrapper with reviewed module names.
set -eo pipefail
: "${EVOX16_PRECHECK:?precheck-owned attempt required}"
MODULES=("$@")
finish() {
    rc=$?
    python3 - "$EVOX16_PRECHECK/precheck-exit.json" "$rc" "${MODULES[@]}" <<'PY'
import json,os,sys,time
path=sys.argv[1]
record={'operation':'focused-precheck','exit':int(sys.argv[2]),'time':time.time(),'modules':sys.argv[3:]}
temp=path+'.runner.tmp'
with open(temp,'x') as f:json.dump(record,f)
os.replace(temp,path)
PY
}
trap finish EXIT
test "${#MODULES[@]}" -gt 0
test "${#MODULES[@]}" -le 64
for module in "${MODULES[@]}"; do
    [[ "$module" =~ ^[A-Za-z0-9_][A-Za-z0-9_.+@-]*$ ]] || { echo INVALID_MODULE_NAME; exit 2; }
    case "$module" in
        updatepackage|otapackage|evolution|dist|droid|all|checkbuild|clean|clobber|installclean|dataclean|images|systemimage|vendorimage|bootimage|target-files-package)
            echo PRECHECK_TARGET_SCOPE_REJECTED; exit 2 ;;
    esac
done
test "$PWD" = /mnt/wsl/evox/src
test -L out
test "$(readlink -f out)" = /mnt/wsl/build/evox-out
test -f vendor/evolution-priv/keys/platform.x509.pem
export WITH_GMS=true
# The inherited envsetup host-name pipeline intentionally stops tr via head.
set +o pipefail
source /mnt/c/XiaomiBuilds/build-setup/evox/env.sh
set -o pipefail
test "$LUNCH_TARGET" = lineage_klimt-cp2a-user || { echo RELEASE_TARGET_MISMATCH; exit 2; }
printf 'PRECHECK COMMAND lunch %s\n' "$LUNCH_TARGET"
lunch "$LUNCH_TARGET"
test "$(get_build_var TARGET_PRODUCT)" = lineage_klimt
test "$(get_build_var TARGET_BUILD_VARIANT)" = user
test "$TARGET_RELEASE" = cp2a
test "$(get_build_var WITH_GMS)" = true
printf 'PRECHECK ENV SOONG_NINJA=%s CCACHE_DIR=%s WITH_GMS=%s\n' "$SOONG_NINJA" "$CCACHE_DIR" "$WITH_GMS"
printf 'PRECHECK COMMAND m -j12'; printf ' %q' "${MODULES[@]}"; printf '\n'
m -j12 "${MODULES[@]}"
