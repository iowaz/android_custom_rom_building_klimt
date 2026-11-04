"""Every path the build pipeline uses. Change locations here only.

The build name comes from the attempt ID (`20261105-attempt01`) or from KLIMT_BUILD. Builds up to evox31 are
named evoxNN; builds from 2026-11-05 on are named by date, YYYYMMDD, and YYYYMMDD.N (N >= 2) for a second
build on the same day.
Windows paths: D:\\android_rom_building is /mnt/d/android_rom_building inside WSL.
"""
import datetime
import os
import re
from pathlib import Path

PIPELINE = Path(__file__).resolve().parent
EVOX_SETUP = PIPELINE.parent                       # build-setup/evox (env.sh, sync.sh, ...)
SNAPSHOTS = PIPELINE.parents[2] / 'manifests' / 'snapshots'   # this repository's manifests/snapshots/<build>.xml
ROOT = Path(os.environ.get('KLIMT_ROOT', '/mnt/d/android_rom_building'))

# Inside WSL, on the build disk (vhdx-images\build.vhdx); /mnt/wsl/evox is a bind mount of /mnt/wsl/build/evox
SRC = Path('/mnt/wsl/evox/src')                    # the Android tree; src/out is a symlink to OUT
OUT = Path('/mnt/wsl/build/evox-out')
ZIP = OUT / 'target/product/klimt/lineage_klimt-img.zip'
LOGS = Path('/mnt/wsl/evox/logs')                  # per build: LOGS/<build>/<attempt>/build.log ...
COMPARE = Path('/mnt/wsl/build/compare')           # reference images (author, b9, live, tools) + extractions
TOOLS = COMPARE / 'tools'
MOVED_PROJECTS = Path('/mnt/wsl/build/evox')       # prepare.py move-renamed: <build>-moved-projects (never deleted)
UPSTREAM_MANIFEST = Path.home() / 'evox-upstream-check' / 'mf'  # prepare.py upstream: Evolution-X/manifest checkout

# On Windows (D:\android_rom_building)
DIAGNOSTICS = ROOT / 'diagnostics' / 'builds'      # per build: readiness, reports, attempt records
OUTPUT_ZIPS = ROOT / 'output-zips'                 # per build: the image ZIP and its flash scripts
PARTITIONS = ROOT / 'backups' / 'PartitionsBackup' # the phone's own partitions (live slot b DTBO/vendor_boot)
PLATFORM_TOOLS = ROOT / 'tools' / 'platform-tools'

HISTORY_BUILD = re.compile(r'evox(\d+)')                      # evox1 ... evox31
DATE_BUILD = re.compile(r'(\d{8})(?:\.([2-9]|[1-9]\d+))?')    # 20261105, 20261105.2
FIRST_DATE_BUILD = '20261105'
ATTEMPT = re.compile(r'(evox\d+|\d{8}(?:\.(?:[2-9]|[1-9]\d+))?)-attempt\d{2,}')


def is_build(name):
    """evoxNN, or YYYYMMDD[.N] for a real date from 2026-11-05 on."""
    if HISTORY_BUILD.fullmatch(name):
        return True
    m = DATE_BUILD.fullmatch(name)
    if not m or m.group(1) < FIRST_DATE_BUILD:
        return False
    try:
        datetime.datetime.strptime(m.group(1), '%Y%m%d')
    except ValueError:
        return False
    return True


def is_date_build(name):
    return is_build(name) and not HISTORY_BUILD.fullmatch(name)


def at_least(build, number):
    """True for evox<number> and later. Every date-named build comes after evox31."""
    if not is_build(build):
        raise ValueError('Invalid build name: ' + repr(build))
    m = HISTORY_BUILD.fullmatch(build)
    return int(m.group(1)) >= number if m else True


def kernel_label(build):
    """The kernel release suffix: evox31 -> ab31, 20261105 -> ab20261105, 20261105.2 -> ab20261105.2."""
    if not is_build(build):
        raise ValueError('Invalid build name: ' + repr(build))
    m = HISTORY_BUILD.fullmatch(build)
    return 'ab' + (str(int(m.group(1))) if m else build)


def build_of(attempt_id):
    m = ATTEMPT.fullmatch(attempt_id)
    if not m or not is_build(m.group(1)):
        raise ValueError('Attempt IDs look like 20261105-attempt01 (or evox31-attempt01), not ' + repr(attempt_id))
    return m.group(1)


def current_build():
    build = os.environ.get('KLIMT_BUILD', '')
    if not is_build(build):
        raise RuntimeError('KLIMT_BUILD must name the build (for example 20261105, or evox31 for history); start.sh sets it')
    return build


def for_build(build):
    """Per-build locations."""
    debug = DIAGNOSTICS / build
    return dict(
        logs=LOGS / build,                 # attempt folders, locks, launch logs (WSL ext4)
        debug=debug,                       # FINAL_SOURCE / BUILD_READY / per-attempt copies (Windows)
        preparation=debug / 'preparation', # prepare.py records: upstream, sync, patch, label, freeze (Windows)
        reports=debug / 'reports',         # verifier reports per attempt and recheck (Windows)
        extract=COMPARE / build,           # image extraction scratch per attempt (WSL ext4, deletable)
        staging=debug / 'delivery',        # verified deliveries per attempt, before promote.py
        delivery=OUTPUT_ZIPS / build,      # the promoted delivery: what you flash
    )
