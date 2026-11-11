"""Hash-bound, fail-closed kernel audit and rollback evidence for local candidates."""
import datetime
import json
from pathlib import Path
import kernel_contract
import rollback_security
import re

REQUIRED = {'ancestry', 'local_delta', 'pkvm_semantics', 'pkvm_types', 'type_abi',
            'protected_exports', 'symbol_membership', 'config', 'module_crc', 'module_layout'}


def file_record(path):
    p = Path(path).resolve()
    return dict(path=str(p), sha256=rollback_security.digest(p))


def revalidate(record):
    p = Path(record['path'])
    if rollback_security.digest(p) != record['sha256']:
        raise ValueError('Candidate evidence hash drift: '+str(p))
    return json.loads(p.read_text())


def validate_audit(data, frozen, baseline_digest):
    wanted = {p: frozen[p] for p in (kernel_contract.KERNEL, 'kernel/xiaomi/klimt-prebuilt', 'vendor/xiaomi/klimt')}
    if data.get('schema') != 1 or data.get('source_heads') != wanted or data.get('baseline_manifest_sha256') != baseline_digest:
        raise ValueError('Kernel audit is not bound to the candidate source/control')
    if not re.fullmatch(r'[0-9a-f]{64}', str(data.get('normalized_config_sha256', ''))):
        raise ValueError('Analyzed normalized kernel configuration digest required')
    checks = data.get('checks', {})
    if set(checks) != REQUIRED or any(c.get('pass') is not True or not c.get('explanation') or not c.get('files') for c in checks.values()):
        raise ValueError('All kernel source/type/pKVM/protected-export/config/module gates must explicitly pass with evidence')
    for check in checks.values():
        for record in check['files']:
            if rollback_security.digest(record['path']) != record['sha256']:
                raise ValueError('Kernel audit proof hash drift: '+record['path'])
    return data


def normalized_config(text):
    """Only the per-build LOCALVERSION may differ from the analyzed configuration."""
    values = [line for line in text.splitlines() if line and not line.startswith('#') and not line.startswith('CONFIG_LOCALVERSION=')]
    return '\n'.join(sorted(values))+'\n'


def validate_compiled_config(audit, config):
    import hashlib
    wanted = audit.get('normalized_config_sha256')
    actual = hashlib.sha256(normalized_config(Path(config).read_text()).encode()).hexdigest()
    if not wanted or actual != wanted:
        raise ValueError('Packaged kernel configuration differs from analyzed configuration')


def freeze_deadline(preparation, now=None):
    started = datetime.datetime.strptime(preparation['control_freeze_utc'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)
    now = now or datetime.datetime.now(datetime.timezone.utc)
    if now < started or now-started > datetime.timedelta(days=7):
        raise ValueError('Control freeze window invalid/expired; revalidate a new control')


def validate_ready(ready, frozen):
    records = ready.get('candidate_evidence')
    if frozen[kernel_contract.KERNEL] != kernel_contract.BASELINE and not records:
        raise ValueError('New kernel requires mandatory candidate evidence')
    if not records:
        return
    prep = revalidate(records['preparation'])
    freeze_deadline(prep)
    if prep['heads'][kernel_contract.KERNEL] != frozen[kernel_contract.KERNEL]:
        raise ValueError('Candidate preparation kernel drift')
    audit = revalidate(records['kernel_audit'])
    validate_audit(audit, frozen, prep['baseline_sha256'])
    baseline_record = revalidate(records['rollback_baseline'])
    if baseline_record.get('schema') != 1 or baseline_record.get('baseline_manifest_sha256') != prep['baseline_sha256']:
        raise ValueError('Rollback control manifest binding missing/mismatched')
    if rollback_security.digest(baseline_record['archive']['path']) != baseline_record['archive']['sha256']:
        raise ValueError('Rollback control archive missing/changed')
    baseline = baseline_record['security']
    if baseline.get('schema') != 1 or baseline.get('actual_source_spl') is None or not baseline.get('avb') or not baseline.get('boot_headers'):
        raise ValueError('Rollback baseline metadata incomplete')
    if ready['security']['platform_security_patch'] != baseline['actual_source_spl']:
        raise ValueError('Controlled candidate actual source SPL differs from control')
