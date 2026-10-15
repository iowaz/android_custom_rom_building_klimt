#!/bin/bash
set -euo pipefail
B=/mnt/c/XiaomiBuilds/build-setup/evox
pgrep -af 'fix15/(monitor15|wait-verify)|build.sh evox15' || true
python3 -B "$B/fix15/health15.py"
