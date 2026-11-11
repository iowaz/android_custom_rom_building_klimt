"""Validate machine-produced ABI, pKVM, config and vendor-contract evidence."""
import hashlib
import json
import re
from pathlib import Path

import abi_analysis


def validate(audit, frozen, retained, tool_sha256, compare_graphs):
    def file(check, name):
        matches = [Path(r['path']) for r in audit['checks'][check]['files'] if Path(r['path']).name == name]
        if len(matches) != 1:
            raise ValueError('Required unique machine proof missing: '+check+'/'+name)
        return matches[0]

    def report(check, name):
        return json.loads(file(check, name).read_text())

    def require(ok, message):
        if not ok:
            raise ValueError(message)

    def passed(data, message):
        require(data.get('pass') is True, message)

    require(bool(retained), 'Frozen retained-symbol contract is empty')
    abi = report('type_abi', 'abi-RESULT.json')
    passed(abi, 'ABI producer failed')
    require(abi.get('exit') == 0, 'ABI producer exit was not zero')
    graph_paths = {}
    actual_untyped = {}
    proof_digests = {r['sha256'] for r in audit['checks']['type_abi']['files']}
    for label in ('old', 'new'):
        graph_paths[label] = file('type_abi', label+'.stg')
        record = abi['inputs'][label]
        coverage = abi_analysis.require_coverage(graph_paths[label].read_text(), retained)
        require(record.get('symbols') == coverage['symbols'] == len(retained), 'ABI retained coverage mismatch')
        require(record.get('untyped') == coverage['untyped'], 'ABI untyped-symbol report mismatch')
        actual_untyped[label] = coverage['untyped']
        require(hashlib.sha256(graph_paths[label].read_bytes()).hexdigest() == record['graph_sha256'], 'ABI graph hash mismatch')
        require(record['tool_sha256'] == tool_sha256, 'ABI extraction tool differs from frozen tool')
        require(bool(record['inputs']) and all(r['sha256'] in proof_digests for r in record['inputs']), 'ABI ELF input evidence incomplete')
    require(compare_graphs(graph_paths['old'], graph_paths['new']) == 0, 'Actual type graph comparison failed')
    require(actual_untyped['old'] == actual_untyped['new'], 'ABI type presence changed')
    if actual_untyped['old']:
        declaration = report('type_abi', 'assembly-declaration-review.json')
        passed(declaration, 'Assembly declaration review failed')
        require(declaration['source_heads']['new'] == frozen['kernel/xiaomi/klimt'], 'Assembly review candidate mismatch')
        require(set(declaration['symbols']) == set(actual_untyped['old']), 'Assembly declaration coverage incomplete')
        for symbol in declaration['symbols'].values():
            require(bool(symbol.get('explanation')) and bool(symbol.get('declarations')) and bool(symbol.get('providers')), 'Assembly declaration/provider review absent')
            for proof in symbol['declarations']+symbol['providers']:
                old = Path(proof['old']).read_bytes(); new = Path(proof['new']).read_bytes()
                require(old == new and hashlib.sha256(old).hexdigest() == proof['sha256'], 'Assembly source contract changed')
                require(proof['sha256'] in proof_digests, 'Assembly source proof is not hash-bound')

    pkvm = report('pkvm_types', 'pkvm-compiled-types.json')
    callbacks = report('pkvm_types', 'pkvm-callback-types.json')
    passed(pkvm, 'pKVM layout producer failed'); passed(callbacks, 'pKVM argument-type producer failed')
    require(pkvm.get('byte_identical_pahole_layout_and_signatures') is True and bool(callbacks.get('types')), 'pKVM layout/type coverage absent')
    expected_types = {'user_pt_regs', 'kvm_hyp_req', 'kvm_hyp_iommu', 'kvm_hyp_iommu_domain',
                      'kvm_iommu_paddr_cache', 'iommu_iotlb_gather', 'arm_smccc_1_2_regs', 'arm_smccc_res', 'list_head'}
    require(set(callbacks['types']) == expected_types, 'pKVM callback argument coverage incomplete')
    for old, new in [('pahole-pkvm-baseline.txt', 'pahole-pkvm-candidate.txt'),
                     ('pkvm-callback-types-old.txt', 'pkvm-callback-types-new.txt')]:
        a = file('pkvm_types', old).read_bytes(); b = file('pkvm_types', new).read_bytes()
        require(bool(a.strip()) and a == b, 'Compiled pKVM type proof differs')
        if old.startswith('pahole-'):
            require(b'struct pkvm_module_ops' in a, 'pKVM ops definition absent')
            require(hashlib.sha256(a).hexdigest() == pkvm['baseline_sha256'] == pkvm['candidate_sha256'], 'pKVM layout report hash mismatch')
        else:
            require(all(re.search(r'\b(?:struct|union)\s+'+name+r'\b', a.decode()) for name in expected_types), 'pKVM callback definition absent')

    crc = report('module_crc', 'candidate-module-crc.json')
    vendor = report('module_crc', 'vendor-module-contract.json')
    passed(crc, 'Module CRC producer failed')
    require(crc.get('mismatches') == {} and crc.get('module_layout_mismatches') == [], 'Module CRC/layout mismatch')
    require(crc.get('unresolved') == vendor.get('baseline_unresolved') == ['mtk_drm_gateic_set_backlight'], 'Unexpected unresolved module symbol')
    require(crc.get('vendor_count') == vendor.get('vendor_count') == len(vendor.get('modules', {})) > 0, 'Vendor module coverage mismatch')
    require(type(vendor.get('baseline_module_layout')) is int and crc.get('module_layout_candidate') == crc.get('module_layout_baseline') == vendor['baseline_module_layout'], 'module_layout contract changed')

    protection = report('protected_exports', 'protected-policy-report.json')
    passed(protection, 'Protected policy producer failed')
    require(protection.get('changed') == [] and bool(protection.get('source_files')) and
            all(p['old'] == p['new'] for p in protection['source_files'].values()), 'Unreviewed protected-policy source change')
    require(not protection['intersections']['newly_restricted_exports'] and not protection['intersections']['kernel_imports_outside_whitelist'], 'New protected export/import restriction')
    require(bool(protection['generated_headers']) and all(h.get('equal') is True and h['old_sha256'] == h['new_sha256'] for h in protection['generated_headers'].values()), 'Generated module protection headers changed')

    membership = report('symbol_membership', 'symbol-membership.json')
    require(membership.get('whitelist') == membership.get('tracked_old') == membership.get('tracked_target') == len(retained), 'Tracked symbol coverage mismatch')
    require(membership.get('out_of_contract_old') == membership.get('out_of_contract_target') == membership.get('newly_untracked') == [], 'Unreviewed out-of-contract symbol')

    status = report('config', 'analysis-status.json')
    require(status.get('state') == 'complete' and status.get('exit') == 0 and status.get('kernel') == frozen['kernel/xiaomi/klimt'], 'Analysis build is failed/stale')
    from candidate_gates import validate_compiled_config
    validate_compiled_config(audit, file('config', '.config'))
    return {'pass': True, 'retained_symbols': len(retained), 'untyped_supplemented': len(actual_untyped['old'])}
