#!/bin/bash
# Invoked only by controller.py after the immutable readiness checks pass.
set -eo pipefail
: "${KLIMT_ATTEMPT:?controller-owned attempt required}"
PIPELINE=$(dirname "$(realpath "${BASH_SOURCE[0]}")")
finish() {
    rc=$?
    python3 - "$KLIMT_ATTEMPT/build-exit.json" "$rc" "$PIPELINE/staging_evidence.py" "$KLIMT_ATTEMPT" <<'PY'
import hashlib,json,os,subprocess,sys,time
path=sys.argv[1]
temp=path+'.runner.tmp'
record={'exit':int(sys.argv[2]),'time':time.time()}
if record['exit']==0:
    archive='/mnt/wsl/build/evox-out/target/product/klimt/lineage_klimt-img.zip'
    h=hashlib.sha256()
    with open(archive,'rb') as f:
        for chunk in iter(lambda:f.read(4*1024*1024),b''):h.update(chunk)
    st=os.stat(archive)
    record.update(zip_sha256=h.hexdigest(),zip_mtime_ns=st.st_mtime_ns,zip_bytes=st.st_size)
    # Staging evidence for simple verification (staging_evidence.py). Exit 0 already proves installclean and
    # the empty-staging assertion ran; a capture failure leaves the compile result alone and makes simple
    # verification stop on missing evidence.
    capture=subprocess.run(['python3','-B',sys.argv[3],sys.argv[4]],capture_output=True,text=True)
    if capture.returncode==0:record['staging_evidence']=json.loads(capture.stdout)
    else:record['staging_evidence_error']=(capture.stdout+capture.stderr)[-2000:]
with open(temp,'x') as f:json.dump(record,f)
os.replace(temp,path)
PY
}
trap finish EXIT
test "$PWD" = /mnt/wsl/evox/src
test -L out
test "$(readlink -f out)" = /mnt/wsl/build/evox-out
test -f vendor/evolution-priv/keys/platform.x509.pem
export WITH_GMS=true
# The inherited envsetup host-name pipeline intentionally stops tr via head.
set +o pipefail
source "$(dirname "$(realpath "${BASH_SOURCE[0]}")")/../env.sh"
set -o pipefail
test "$LUNCH_TARGET" = lineage_klimt-cp2a-user || { echo RELEASE_TARGET_MISMATCH; exit 2; }
printf 'COMMAND lunch %s\n' "$LUNCH_TARGET"
lunch "$LUNCH_TARGET"
test "$(get_build_var TARGET_PRODUCT)" = lineage_klimt
test "$(get_build_var TARGET_BUILD_VARIANT)" = user
test "$TARGET_RELEASE" = cp2a
test "$(get_build_var WITH_GMS)" = true
printf 'ENV SOONG_NINJA=%s CCACHE_DIR=%s WITH_GMS=%s\n' "$SOONG_NINJA" "$CCACHE_DIR" "$WITH_GMS"
# evox16 shipped a stray Telecom.apk that a module-goal build (m Telecom) had installed into the
# staging directories; images are packed from those directories, not from the install list.
# installclean removes every staged partition so the image holds only this product's installs.
printf 'COMMAND m -j12 installclean\n'
m -j12 installclean
for d in system system_ext product vendor odm vendor_dlkm system_dlkm odm_dlkm; do
    test ! -e "out/target/product/klimt/$d" || { echo "STAGING_NOT_CLEAN $d"; exit 2; }
done
printf 'COMMAND m -j12 updatepackage\n'
m -j12 updatepackage
