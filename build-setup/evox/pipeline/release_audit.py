"""Generate exact post-build kernel evidence before the normal image verifier runs."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import abi_analysis
import candidate_gates as gates
import elf_contract
import kernel_contract
import paths
import preserve_kernel_audit
import reviewed_readiness


def unique(audit, check, name):
    matches = [Path(r['path']) for r in audit['checks'][check]['files'] if Path(r['path']).name == name]
    if len(matches) != 1:
        raise ValueError('Required unique admitted proof: '+check+'/'+name)
    return matches[0]


def json_report(path, value):
    Path(path).write_text(json.dumps(value, indent=2))
    return Path(path)


def active_config(text):
    return {l.split('=',1)[0]:l.split('=',1)[1] for l in text.splitlines() if l.startswith('CONFIG_') and '=' in l}


def compare_vendor_contract(symvers, contract):
    crcs = {p[1]:int(p[0],16) for line in Path(symvers).read_text().splitlines() if len(p:=line.split()) >= 2}
    mismatches, layout, unresolved = {}, [], set()
    for name, module in contract['modules'].items():
        for symbol, crc in module['versions'].items():
            if symbol == 'module_layout' and crcs.get(symbol) != crc:
                layout.append(name)
            if symbol in crcs and crcs[symbol] != crc:
                mismatches.setdefault(symbol,[]).append(name)
            if symbol not in crcs and symbol not in contract['exports']:
                unresolved.add(symbol)
    ok = not mismatches and not layout and sorted(unresolved) == contract['baseline_unresolved']
    if not ok:
        raise ValueError('Exact release vendor module CRC/layout/import contract failed')
    return dict(schema=1, **{'pass':True}, vendor_count=contract['vendor_count'], mismatches=mismatches,
                unresolved=sorted(unresolved), module_layout_mismatches=layout,
                module_layout_candidate=crcs.get('module_layout'), module_layout_baseline=contract['baseline_module_layout'])


def callback_dump(parts, baseline):
    # Preserve the existing report's separators, without normalizing any type definition.
    for result in (''.join(parts), '\n'.join(parts), '\n\n'.join(parts), ''.join(p+'\n' for p in parts)):
        if result == baseline:
            return result
    raise ValueError('Exact release pKVM callback argument types changed')


def tracked_symbols(repository, revision):
    git=['git','-C',str(repository)]
    names=subprocess.check_output(git+['ls-tree','-r','--name-only',revision,'android'],text=True).splitlines()
    names=[n for n in names if n.startswith('android/abi_gki_aarch64') and 'klimt' not in n and not n.endswith(('.xml','.stg'))]
    if not names:raise ValueError('Frozen official tracked-symbol lists are missing')
    result=set()
    for name in names:
        text=subprocess.check_output(git+['show',revision+':'+name],text=True)
        for line in text.splitlines():
            value=line.split('#',1)[0].strip()
            if value and not value.startswith('['):result.add(value)
    return result


def membership(whitelist, old, new):
    report=dict(whitelist=len(whitelist),tracked_old=len(whitelist&old),tracked_target=len(whitelist&new),
                out_of_contract_old=sorted(whitelist-old),out_of_contract_target=sorted(whitelist-new),
                newly_untracked=sorted((whitelist&old)-new))
    if not whitelist or report['out_of_contract_old'] or report['out_of_contract_target']:
        raise ValueError('Release retained symbols are outside the admitted official tracked contract')
    return report


def produce(admitted_record, ready, obj, output, source, context):
    obj, output, source = Path(obj), Path(output).resolve(), Path(source)
    if not output.is_relative_to(paths.DIAGNOSTICS.resolve()):
        raise ValueError('Release analysis must be preserved in diagnostics/builds')
    output.mkdir(parents=True, exist_ok=False)
    admitted_path = Path(admitted_record['path'])
    admitted = gates.revalidate(admitted_record)
    if any(not Path(r['path']).resolve().is_relative_to(paths.DIAGNOSTICS.resolve())
           for c in admitted['checks'].values() for r in c['files']):
        admitted_path = preserve_kernel_audit.preserve(admitted_path, output/'admitted')
        admitted = json.loads(admitted_path.read_text())
    frozen = ready['reviewed_project_heads']
    gates.validate_audit(admitted, frozen, admitted['baseline_manifest_sha256'])
    expected = kernel_contract.source_expectation(frozen, ready['build'], source)
    if ready['kernel_expectation'] != expected or (obj/'include/config/kernel.release').read_text().strip() != expected['release']:
        raise ValueError('Release outputs do not match the frozen source-derived kernel identity')
    if hashlib.sha256(gates.normalized_config((obj/'.config').read_text()).encode()).hexdigest() != admitted['normalized_config_sha256']:
        raise ValueError('Release active configuration differs from the admitted contract; explicit review required')
    inputs = output/'inputs'; inputs.mkdir()
    files = [obj/'vmlinux',obj/'.config',obj/'Module.symvers',obj/'include/config/kernel.release',*sorted(obj.rglob('*.ko'))]
    protection = json.loads(unique(admitted,'protected_exports','protected-policy-report.json').read_text())
    files += [obj/'include/generated'/name for name in protection['generated_headers']]
    copied = []
    for path in files:
        destination = inputs/path.relative_to(obj);destination.parent.mkdir(parents=True,exist_ok=True)
        before = gates.file_record(path);shutil.copyfile(path,destination);after = gates.file_record(destination)
        if before['sha256'] != after['sha256']:
            raise ValueError('Release input copy hash mismatch')
        copied.append(dict(source_path=before['path'],source_sha256=before['sha256'],preserved=after))
    json_report(output/'production-inputs.json',copied)
    old_result = json.loads(unique(admitted,'type_abi','abi-RESULT.json').read_text())
    expected_modules = {Path(r['path']).name for r in old_result['inputs']['new']['inputs'] if r['path'].endswith('.ko')}
    modules = sorted(inputs.rglob('*.ko'))
    if len(modules) != len(expected_modules) or {p.name for p in modules} != expected_modules:
        raise ValueError('Release GKI debug module set differs from admission')
    crc_elf = elf_contract.validate(inputs/'Module.symvers',[inputs/'vmlinux',*modules])
    json_report(output/'elf-crc-contract.json',crc_elf)
    tools = source/'prebuilts/kernel-build-tools/linux-x86/bin'
    analysis = output/'analysis';analysis.mkdir()
    shutil.copyfile(unique(admitted,'type_abi','old.stg'),analysis/'old.stg')
    retained = kernel_contract.retained_symbols(frozen,source)
    refs=json.loads(unique(admitted,'ancestry','kernel-refs.json').read_text())
    json_report(output/'symbol-membership.json',membership(retained,
        tracked_symbols(source/kernel_contract.KERNEL,refs['true_lts_base']),
        tracked_symbols(source/kernel_contract.KERNEL,refs['target'])))
    new = abi_analysis.extract(tools/'stg',inputs,retained,analysis/'new.stg')
    old = old_result['inputs']['old']
    if old['tool_sha256'] != new['tool_sha256'] or abi_analysis.require_coverage((analysis/'old.stg').read_text(),retained)['symbols'] != len(retained):
        raise ValueError('Release ABI extraction tool/old coverage differs from the admitted contract')
    with (analysis/'stgdiff.log').open('w') as log:
        comparison = subprocess.run([str(tools/'stgdiff'),'-s',str(analysis/'old.stg'),'-s',str(analysis/'new.stg'),
                                     '-f','small','-o',str(output/'abi-type-diff.txt')],stdout=log,stderr=subprocess.STDOUT)
    if comparison.returncode:
        raise ValueError('Exact release ABI comparison failed')
    declaration = unique(admitted,'type_abi','assembly-declaration-review.json')
    json_report(output/'abi-RESULT.json',dict(exit=0,**{'pass':True},inputs=dict(old=old,new=new),declaration_review=str(declaration)))
    json_report(output/'abi-old.inputs.json',old);json_report(output/'abi-new.inputs.json',new)
    pahole = lambda name: subprocess.check_output([str(tools/'pahole'),'-C',name,str(inputs/'vmlinux')],text=True)
    baseline_ops = unique(admitted,'pkvm_types','pahole-pkvm-baseline.txt')
    ops = pahole('pkvm_module_ops')
    if ops != baseline_ops.read_text():
        raise ValueError('Exact release pKVM module ops layout/signatures changed')
    (output/'pahole-pkvm-candidate.txt').write_text(ops)
    ops_hash = hashlib.sha256(ops.encode()).hexdigest()
    json_report(output/'pkvm-compiled-types.json',dict(schema=1,**{'pass':True},
        byte_identical_pahole_layout_and_signatures=True,baseline_sha256=ops_hash,candidate_sha256=ops_hash))
    callbacks = json.loads(unique(admitted,'pkvm_types','pkvm-callback-types.json').read_text())
    baseline_callbacks = unique(admitted,'pkvm_types','pkvm-callback-types-old.txt')
    (output/'pkvm-callback-types-new.txt').write_text(callback_dump([pahole(n) for n in callbacks['types']],baseline_callbacks.read_text()))
    json_report(output/'pkvm-callback-types.json',dict(**{'pass':True},types=callbacks['types']))
    vendor = unique(admitted,'module_crc','vendor-module-contract.json')
    json_report(output/'candidate-module-crc.json',compare_vendor_contract(inputs/'Module.symvers',json.loads(vendor.read_text())))
    for rel, values in protection['source_files'].items():
        data = subprocess.check_output(['git','-C',str(source/kernel_contract.KERNEL),'show',frozen[kernel_contract.KERNEL]+':'+rel])
        if hashlib.sha256(data).hexdigest() != values['new']:
            raise ValueError('Frozen protected policy source changed')
    for name, values in protection['generated_headers'].items():
        record = gates.file_record(inputs/'include/generated'/name)
        if record['sha256'] != values['new_sha256']:
            raise ValueError('Release generated module-protection header changed')
        values['release_path'] = record['path']
    json_report(output/'protected-policy-report.json',protection)
    previous_config = active_config(unique(admitted,'config','.config').read_text())
    actual_config = active_config((inputs/'.config').read_text())
    json_report(output/'generated-config-delta.json',{k:[previous_config.get(k),actual_config.get(k)]
        for k in previous_config.keys()|actual_config.keys() if previous_config.get(k)!=actual_config.get(k)})
    json_report(output/'analysis-config-reviewed.json',dict(kernel=frozen[kernel_contract.KERNEL],
        config_sha256=gates.file_record(inputs/'.config')['sha256'],expected_normalized_sha256=admitted['normalized_config_sha256'],
        explanation='Resolved active options must equal the admitted config. Only source-derived LOCALVERSION is normalized.'))
    json_report(output/'analysis-status.json',dict(kernel=frozen[kernel_contract.KERNEL],state='complete',exit=0,
        method='Versioned post-build analysis of preserved exact release debug ELFs'))
    json_report(output/'analysis-invocation.json',dict(context=context,kernel_expectation=expected,
        admitted_audit=admitted_record,preserved_admission=gates.file_record(admitted_path)))
    audit = copy.deepcopy(admitted)
    def check(name, explanation, files):
        audit['checks'][name]=dict(**{'pass':True},explanation=explanation,
            files=[gates.file_record(p) for p in dict.fromkeys(map(Path,files))])
    check('pkvm_types','Exact production ELF preserves admitted pKVM ops and all callback argument types.',
          [output/'pkvm-compiled-types.json',baseline_ops,output/'pahole-pkvm-candidate.txt',
           output/'pkvm-callback-types.json',baseline_callbacks,output/'pkvm-callback-types-new.txt'])
    typed = [output/n for n in ('abi-RESULT.json','abi-old.inputs.json','abi-new.inputs.json','abi-type-diff.txt')]
    typed += [analysis/'old.stg',analysis/'new.stg',declaration]
    typed += [Path(r['path']) for record in (old,new) for r in record['inputs']]
    for item in json.loads(declaration.read_text())['symbols'].values():
        for proof in item['declarations']+item['providers']:typed += [Path(proof['old']),Path(proof['new'])]
    check('type_abi','Complete retained old-to-exact-release type contract; unchanged assembly declaration/provider evidence.',typed)
    check('symbol_membership','Retained symbols are recomputed against the exact admitted official base/target tracked lists.',
          [output/'symbol-membership.json'])
    check('protected_exports','Frozen source policy and exact release generated headers preserve the admitted restrictions.',
          [output/'protected-policy-report.json',unique(admitted,'protected_exports','module-policy-implementation.diff'),vendor,
           *[inputs/'include/generated'/n for n in protection['generated_headers']]])
    check('config','Resolved release config equals pre-admitted active policy apart from its frozen-source build label.',
          [output/n for n in ('generated-config-delta.json','analysis-config-reviewed.json','analysis-invocation.json',
                             'analysis-status.json','production-inputs.json')]+[inputs/'.config'])
    crc_files = [output/'candidate-module-crc.json',vendor,inputs/'Module.symvers',output/'elf-crc-contract.json']
    check('module_crc','All stock vendor CRCs/imports match the ELF-validated exact release symbol table.',crc_files)
    provenance = output/'source-tools';provenance.mkdir();shutil.copyfile(paths.PIPELINE/'legacy/musthold.sh',provenance/'musthold.sh')
    check('module_layout','Every stock module_layout CRC matches, with no excluded symbol.',crc_files+[provenance/'musthold.sh'])
    candidate = json_report(output/'generated-kernel-audit.json',audit)
    final = preserve_kernel_audit.preserve(candidate,output/'sealed')
    gates.validate_audit(json.loads(final.read_text()),frozen,admitted['baseline_manifest_sha256'])
    return final


def context(attempt):
    import controller as c
    ready=json.loads((attempt/'BUILD_READY.json').read_text())
    exit_record=json.loads((attempt/'build-exit.json').read_text())
    if exit_record.get('exit') != 0:
        raise ValueError('Release audit requires successful full image compilation')
    heads=c.ready_heads(ready)
    if c.manifest_heads((attempt/'prebuild.xml').read_bytes()) != heads or c.manifest_heads((attempt/'postbuild.xml').read_bytes()) != heads:
        raise ValueError('Release audit source manifests differ from admitted heads')
    return dict(schema=1,original_ready_sha256=c.sha(attempt/'BUILD_READY.json'),
        source_snapshot_sha256=c.sha(attempt/'prebuild.xml'),build_exit_sha256=c.sha(attempt/'build-exit.json'),
        archive_sha256=exit_record['zip_sha256'],tooling_sha256=c.tooling_hashes())


def validate_update(update, expected_context, original, load=gates.revalidate, validate_candidate=gates.validate_ready):
    if update.get('schema') != 1 or update.get('automatic') is not True or update.get('context') != expected_context:
        raise ValueError('Post-build audit update does not bind the producing source/build/tooling context')
    old=load(original['candidate_evidence']['kernel_audit']);new=load(update['kernel_audit_update'])
    if old['normalized_config_sha256'] != new['normalized_config_sha256']:
        raise ValueError('Automatic release analysis cannot change the admitted configuration policy')
    return reviewed_readiness.apply(original,update,load,validate_candidate)


def effective_ready(attempt, original):
    import controller as c
    c.require_tooling_frozen(attempt)
    update=json.loads((attempt/'release-audit-update.json').read_text())
    return validate_update(update,context(attempt),original)


def prepare_for_attempt(attempt, admitted_override=None, output=None):
    """Caller owns source.lock; this function never compiles or modifies packaged output."""
    import controller as c
    attempt=Path(attempt)
    original=json.loads((attempt/'BUILD_READY.json').read_text())
    if not original.get('candidate_evidence'):
        return None
    automatic=admitted_override is None
    if automatic:
        c.require_tooling_frozen(attempt)
        if (attempt/'release-audit-update.json').exists():
            effective_ready(attempt,original)
            return Path(json.loads((attempt/'release-audit-update.json').read_text())['kernel_audit_update']['path'])
    ctx=context(attempt)
    heads=c.ready_heads(original);c.live_heads(heads)
    admitted=original['candidate_evidence']['kernel_audit'] if automatic else gates.file_record(admitted_override)
    prep=gates.revalidate(original['candidate_evidence']['preparation'])
    if gates.revalidate(admitted)['baseline_manifest_sha256'] != prep['baseline_sha256']:
        raise ValueError('Release admission control differs from the producing preparation')
    destination=Path(output) if output else paths.for_build(c.BUILD)['debug']/attempt.name/'release-audit'
    audit=produce(admitted,original,c.O/'target/product/klimt/obj/KERNEL_OBJ',destination,c.S,ctx)
    c.live_heads(heads)
    update=dict(schema=1,automatic=automatic,context=ctx,
                kernel_audit_previous_sha256=original['candidate_evidence']['kernel_audit']['sha256'],
                kernel_audit_update=gates.file_record(audit))
    json_report(destination/'PRODUCTION.json',update)
    if automatic:
        validate_update(update,ctx,original)
        with (attempt/'release-audit-update.json').open('x') as out:json.dump(update,out,indent=2)
    return audit


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('attempt',type=Path)
    ap.add_argument('--admitted-audit',type=Path,help='Manual evidence preparation only; requires an explicit verifier tool review later')
    ap.add_argument('--output',type=Path)
    args=ap.parse_args()
    import controller as c
    with c.lock(c.L/'source.lock'):
        if c.foreign_processes():raise RuntimeError('Build/extraction is active')
        print(prepare_for_attempt(args.attempt,args.admitted_audit,args.output))


if __name__ == '__main__':main()
