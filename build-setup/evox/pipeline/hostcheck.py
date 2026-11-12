"""Stop a Linux-only pipeline command early, with the WSL command to use instead.

Imported before fcntl, controller or any module that needs the Linux build environment. Standard library only.
A wrong host is a tooling error: exit 2, nothing created.
"""
import sys
from pathlib import PurePath

DISTRO = 'Ubuntu-24.04'


def wsl_command(script, args=()):
    """The equivalent command for this repository's clone under D:\\android_rom_building."""
    text = str(script).replace('\\', '/')
    marker = 'android_rom_building/'
    linux = '/mnt/d/android_rom_building/' + text[text.index(marker)+len(marker):] if marker in text else text
    import os
    build = os.environ.get('KLIMT_BUILD')
    prefix = ['env', 'KLIMT_BUILD=' + build] if build else []
    return ' '.join(['wsl.exe', '-d', DISTRO, '--', *prefix, 'python3', '-B', linux, *[str(a) for a in args]])


def require_linux(script, platform=None, stream=None):
    platform = sys.platform if platform is None else platform
    if platform.startswith('linux'):
        return
    stream = sys.stderr if stream is None else stream
    stream.write('ENVIRONMENT ERROR: ' + PurePath(str(script).replace('\\', '/')).name +
                 ' requires Linux (the build tree, locks and tools live in WSL); detected ' + platform + ' Python.\n'
                 'Run it in the configured WSL distro, for example:\n  ' + wsl_command(script, sys.argv[1:]) + '\n'
                 'Nothing was created.\n')
    raise SystemExit(2)
