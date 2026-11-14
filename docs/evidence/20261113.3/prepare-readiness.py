from pathlib import Path
import subprocess,os
B=Path('/mnt/d/android_rom_building');P=B/'repositories/android_custom_rom_building_klimt/build-setup/evox/pipeline'
D=B/'diagnostics/builds/20261113.3'
os.environ['KLIMT_BUILD']='20261113.3'
assert not (D/'BUILD_READY.json').exists()
subprocess.run(['python3','-B',str(P/'ready.py'),str(D/'20261113.3-frozen.xml'),'--mode','full',
 '--reason','Owner-requested keybox monitor revision across framework, system service, Settings and translations',
 '--kernel-audit',str(B/'diagnostics/builds/20261113.2/kernel-audit-carried.json'),'--rollback-baseline',str(B/'diagnostics/builds/20261113.2/control-security.json'),
 '--gate','keybox implementation and review='+str(B/'diagnostics/features/keybox-monitor/20261113.3/IMPLEMENTATION.json')],check=True)
