"""Read-only feature presence check after the attempt's full image verification."""
from pathlib import Path
import hashlib, json, re, struct, subprocess, zipfile
BUILD='20261113.2'
BASE=Path('/mnt/d/android_rom_building')
ROOT=Path('/mnt/wsl/evox/src')
EXTRACT=Path('/mnt/wsl/build/compare')/BUILD/(BUILD+'-attempt01')
REPORT=BASE/'diagnostics/builds'/BUILD/'reports'/(BUILD+'-attempt01')
OUT=BASE/'diagnostics/builds'/BUILD/'KEYBOX_MONITOR_IMAGE_CHECK.json'

def classes_in_dex(data):
    if not data.startswith(b'dex\n'): raise ValueError('Not standard DEX')
    ns, so, nt, to = struct.unpack_from('<IIII',data,56)
    nc, co=struct.unpack_from('<II',data,96)
    def string(index):
        offset=struct.unpack_from('<I',data,so+4*index)[0]
        while data[offset]&0x80:offset+=1
        offset+=1
        return data[offset:data.index(b'\0',offset)].decode('utf-8',errors='replace')
    result=set()
    for n in range(nc):
        type_index=struct.unpack_from('<I',data,co+32*n)[0]
        string_index=struct.unpack_from('<I',data,to+4*type_index)[0]
        result.add(string(string_index))
    return result

def dex_classes(path):
    found=set()
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if re.fullmatch(r'classes\d*\.dex',name): found.update(classes_in_dex(archive.read(name)))
    if not found: raise ValueError('No DEX class definitions: '+str(path))
    return found

def find(relative):
    candidates=[EXTRACT/'fs/system'/relative,EXTRACT/'fs/system/system'/relative]
    matches=[p for p in candidates if p.is_file()]
    if len(matches)!=1: raise ValueError('Cannot uniquely locate '+relative)
    return matches[0]

def main():
    result=json.loads((REPORT/'RESULTS.json').read_text())
    if result['historical']['musthold']!='pass' or not all(
            c.get('pass') is True for c in result['historical']['checks']):
        raise ValueError('Full image checks have not passed')
    if len(result.get('supplemental',[]))!=7 or any(c['exit']!=0 for c in result['supplemental']):
        raise ValueError('Supplemental image checks have not passed')
    paths={
        'framework':find('framework/framework.jar'),
        'services':find('framework/services.jar'),
        'framework_resources':find('framework/framework-res.apk'),
    }
    settings=list((EXTRACT/'fs').glob('*/**/priv-app/Settings/Settings.apk'))
    settings+=list((EXTRACT/'fs').glob('*/**/priv-app/SettingsGoogle/SettingsGoogle.apk'))
    if len(settings)!=1: raise ValueError('Cannot uniquely locate Settings.apk')
    paths['settings']=settings[0]
    checks=[]
    def check(name,condition):
        checks.append({'name':name,'pass':bool(condition)})
        if not condition:raise ValueError(name)
    framework=dex_classes(paths['framework']); services=dex_classes(paths['services'])
    check('Framework monitor contract defined',
          'Landroid/security/trickystore/KeyboxMonitor;' in framework)
    check('System-owned monitor defined',
          'Lcom/android/server/spoof/TrickyStoreKeyboxMonitor;' in services)
    check('Shared certificate inspector defined',
          'Lcom/android/server/spoof/KeyboxInspector;' in services)
    check('Read-only keybox operation engine defined',
          'Lcom/android/server/spoof/KeyboxOperations;' in services)
    check('TrickyStore settings defined',
          'Lorg/evolution/settings/fragments/miscellaneous/TrickyStore;' in dex_classes(paths['settings']))
    aapt=ROOT/'out/host/linux-x86/bin/aapt2'
    for kind,names in {
        'settings':['ts_monitor_enabled','ts_monitor_interval','ts_monitor_minutes','ts_monitor_hours',
                    'ts_monitor_one_hour','ts_monitor_schedule','ts_monitor_notifications',
                    'ts_monitor_notify_every','ts_monitor_notify_unusable','ts_monitor_notify_failed'],
        'framework_resources':['ts_monitor_channel_results','ts_monitor_channel_recovery',
                               'ts_monitor_expired','ts_monitor_revoked','ts_monitor_failed',
                               'ts_monitor_reload_incomplete','ts_monitor_paused']}.items():
        resources=subprocess.check_output([str(aapt),'dump','resources',str(paths[kind])],text=True)
        for name in names:check(kind+': '+name,'string/'+name in resources)
        localized = 'ts_monitor_notify_failed' if kind == 'settings' else 'ts_monitor_failed'
        match = re.search(r'^    resource [^\n]* string/'+localized+r'\n(.*?)(?=^    resource|\Z)',
                          resources, re.M | re.S)
        if not match: raise ValueError('Cannot locate localized monitor resource')
        for locale in ['en-rUS','pt-rBR']:
            check(kind+': '+locale+' monitor translation', '('+locale+')' in match.group(1))
    output={'build':BUILD,'runtime_validated':False,'archive_sha256':result['archive_sha256'],
            'checks':checks,'files':{name:{'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
                                   for name,path in paths.items()}}
    OUT.write_text(json.dumps(output,indent=2)+'\n')
    print('PACKAGED KEYBOX MONITOR:',len(checks),'checks pass;',OUT)

if __name__=='__main__':main()
