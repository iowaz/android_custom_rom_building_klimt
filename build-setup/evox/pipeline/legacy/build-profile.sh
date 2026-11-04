#!/bin/bash
# Sourced by the legacy checks that depend on the build. KLIMT_BUILD is evoxNN (up to evox31) or, from
# 2026-11-05 on, a date: YYYYMMDD, or YYYYMMDD.N (N >= 2) for a second build the same day (paths.py checks the
# date itself). Sets BUILD_PROFILE (empty if invalid) and KERNEL_LABEL (evox31: ab31, 20261105: ab20261105).
# build_at_least N: true for evoxN and later, and for every date-named build (all of them come after evox31).
BUILD_PROFILE=${KLIMT_BUILD:-evox25}; BUILD_SEQ=; KERNEL_LABEL=
if [[ $BUILD_PROFILE =~ ^evox([0-9]+)$ ]]; then
  BUILD_SEQ=$((10#${BASH_REMATCH[1]})); KERNEL_LABEL=ab$BUILD_SEQ
elif [[ $BUILD_PROFILE =~ ^[0-9]{8}(\.([2-9]|[1-9][0-9]+))?$ ]]; then
  KERNEL_LABEL=ab$BUILD_PROFILE
else
  BUILD_PROFILE=
fi
build_at_least(){ [ -n "$BUILD_PROFILE" ] && { [ -z "$BUILD_SEQ" ] || (( BUILD_SEQ >= $1 )); }; }
