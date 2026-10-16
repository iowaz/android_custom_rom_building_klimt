"""Every path the build pipeline uses. Change locations here only.

The build name (evox18, evox19, ...) comes from the attempt ID (`evox18-attempt01`) or from KLIMT_BUILD.
Windows paths: D:\\android_rom_building is /mnt/d/android_rom_building inside WSL.
"""
import os
import re
from pathlib import Path

PIPELINE = Path(__file__).resolve().parent
EVOX_SETUP = PIPELINE.parent                       # build-setup/evox (env.sh, sync.sh, ...)
ROOT = Path(os.environ.get('KLIMT_ROOT', '/mnt/d/android_rom_building'))

# Inside WSL, on the build disk (vhdx-images\build.vhdx); /mnt/wsl/evox is a bind mount of /mnt/wsl/build/evox
SRC = Path('/mnt/wsl/evox/src')                    # the Android tree; src/out is a symlink to OUT
OUT = Path('/mnt/wsl/build/evox-out')
ZIP = OUT / 'target/product/klimt/lineage_klimt-img.zip'
LOGS = Path('/mnt/wsl/evox/logs')                  # per build: LOGS/<build>/<attempt>/build.log ...
COMPARE = Path('/mnt/wsl/build/compare')           # reference images (author, b9, live, tools) + extractions
TOOLS = COMPARE / 'tools'

# On Windows (D:\android_rom_building)
DIAGNOSTICS = ROOT / 'diagnostics' / 'builds'      # per build: readiness, reports, attempt records
OUTPUT_ZIPS = ROOT / 'output-zips'                 # per build: the image ZIP and its flash scripts
PARTITIONS = ROOT / 'backups' / 'PartitionsBackup' # the phone's own partitions (live slot b DTBO/vendor_boot)
PLATFORM_TOOLS = ROOT / 'tools' / 'platform-tools'

ATTEMPT = re.compile(r'(evox\d+)-attempt\d{2,}')


def build_of(attempt_id):
    m = ATTEMPT.fullmatch(attempt_id)
    if not m:
        raise ValueError('Attempt IDs look like evox18-attempt01, not ' + repr(attempt_id))
    return m.group(1)


def current_build():
    build = os.environ.get('KLIMT_BUILD', '')
    if not re.fullmatch(r'evox\d+', build):
        raise RuntimeError('KLIMT_BUILD must name the build (for example evox18); start.sh sets it')
    return build


def for_build(build):
    """Per-build locations."""
    debug = DIAGNOSTICS / build
    return dict(
        logs=LOGS / build,                 # attempt folders, locks, launch logs (WSL ext4)
        debug=debug,                       # FINAL_SOURCE / BUILD_READY / per-attempt copies (Windows)
        reports=debug / 'reports',         # verifier reports per attempt and recheck (Windows)
        extract=COMPARE / build,           # image extraction scratch per attempt (WSL ext4, deletable)
        staging=debug / 'delivery',        # verified deliveries per attempt, before promote.py
        delivery=OUTPUT_ZIPS / build,      # the promoted delivery: what you flash
    )
