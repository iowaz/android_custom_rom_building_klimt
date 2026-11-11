"""Expected kernel identity from immutable source, never from the image under test."""
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

import paths

KERNEL = 'kernel/xiaomi/klimt'
DEVICE = 'device/xiaomi/klimt'
BASELINE = 'f6a5b29f9fe59e4849680d50232f8b5758aa8c11'
HOST = 'pangu-build-component-system-247-r6kfm'
STAMP = '#1 SMP PREEMPT Thu Aug 6 00:00:00 UTC 2026'


def one(pattern, text, name):
    values = re.findall(pattern, text, re.M)
    if len(values) != 1:
        raise ValueError('Expected exactly one source field: ' + name)
    return values[0]


def derive(makefile, common, metadata, head, build):
    if not re.fullmatch(r'[0-9a-f]{40}', head):
        raise ValueError('Kernel head must be an exact commit')
    version = '.'.join(one(r'^' + key + r'\s*=\s*(\d+)\s*$', makefile, key)
                       for key in ('VERSION', 'PATCHLEVEL', 'SUBLEVEL'))
    extra = one(r'^EXTRAVERSION\s*=([^\n]*)$', makefile, 'EXTRAVERSION').strip()
    branch = one(r'^BRANCH=(\S+)$', common, 'BRANCH')
    generation = one(r'^KMI_GENERATION=(\d+)$', common, 'KMI_GENERATION')
    if branch != 'android15-6.6' or generation != '8' or not version.startswith('6.6.'):
        raise ValueError('Klimt requires android15-6.6 KMI generation 8')
    local = one(r'^CONFIG_LOCALVERSION="([^"]+)"$', metadata, 'CONFIG_LOCALVERSION')
    wanted = f'-android15-{generation}-g{head[:12]}-{paths.kernel_label(build)}'
    if local != wanted or not re.search(r'^# CONFIG_LOCALVERSION_AUTO is not set$', metadata, re.M):
        raise ValueError('Device kernel SHA/build label/AUTO disagrees with frozen source')
    if head not in metadata:
        raise ValueError('Device metadata lacks full kernel source SHA')
    release = version + extra + local
    return dict(schema=1, kernel_head=head, build=build, branch=branch,
                kmi_generation=int(generation), release=release,
                banner_prefix=f'Linux version {release} (builder@{HOST}) ', banner_suffix=STAMP)


def source_expectation(frozen, build, src=None):
    root = Path(src) if src is not None else paths.SRC
    def read(project, rel):
        return subprocess.check_output(['git', '-C', str(root/project), 'show',
                                        frozen[project] + ':' + rel], text=True)
    inputs = dict(makefile=read(KERNEL, 'Makefile'), common=read(KERNEL, 'build.config.common'),
                  metadata=read(DEVICE, 'configs/kernel/metadata.config'))
    result = derive(**inputs, head=frozen[KERNEL], build=build)
    result['device_head'] = frozen[DEVICE]
    result['source_sha256'] = {k: hashlib.sha256(v.encode()).hexdigest() for k, v in inputs.items()}
    return result


def historical(build):
    """Immutable old profiles remain usable for their original artifacts only."""
    if paths.is_date_build(build) and build > '20261108':
        raise ValueError('New builds require a frozen-source kernel expectation')
    release = f'6.6.142-android15-8-g{BASELINE[:12]}-{paths.kernel_label(build)}'
    return dict(build=build, kernel_head=BASELINE, release=release,
                banner_prefix=f'Linux version {release} (builder@{HOST}) ', banner_suffix=STAMP)


def validate_banner(banner, build, expected=None):
    expected = historical(build) if expected is None else expected
    if expected.get('build') != build or not banner.startswith(expected['banner_prefix']) or not banner.rstrip().endswith(expected['banner_suffix']):
        raise ValueError('Kernel identity differs from frozen source and selected build')


def environment_expectation():
    p = os.environ.get('EVOX_READY')
    return json.loads(Path(p).read_text()).get('kernel_expectation') if p else None
