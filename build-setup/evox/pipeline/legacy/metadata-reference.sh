#!/bin/bash
# Shared expectations for the two metadata checks inherited from evox7/evox9.
source "$(dirname "${BASH_SOURCE[0]}")/build-profile.sh" || return 2
if [ -z "$BUILD_PROFILE" ]; then
  echo 'Invalid KLIMT_BUILD metadata profile' >&2
  return 2
fi
REFERENCE_FP='google/bluejay_beta/bluejay:CANARY/ZP11.260918.007/16484274:user/release-keys'
REFERENCE_VENDOR_SPL=2026-02-01
if build_at_least 26; then
  REFERENCE_FP='Xiaomi/klimt_global/klimt:17/OS3.3.260806.171839609/OS3.0.335.0.XOSMIXM:user/release-keys'
  REFERENCE_VENDOR_SPL=2026-10-05
fi
reference_fingerprint(){ grep -qxF "ro.build.fingerprint=$REFERENCE_FP" "$1"; }
reference_vendor_spl(){ grep -qxF "ro.vendor.build.security_patch=$REFERENCE_VENDOR_SPL" "$1"; }
