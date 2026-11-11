"""Reuse an unchanged audited kernel contract through a verified, hash-bound control."""
import argparse
import copy
import json
from pathlib import Path

import candidate_gates
import kernel_artifact
import kernel_contract
import rollback_security

CONTRACT = (kernel_contract.KERNEL, 'kernel/xiaomi/klimt-prebuilt', 'vendor/xiaomi/klimt')


def validate(audit, frozen, load, parent_check, heads_from_manifest, file_sha=rollback_security.digest,
             artifact_check=kernel_artifact.validate_receipt):
    chain = audit['kernel_carry']
    parent = load(chain['audit'])
    control = load(chain['control_results'])
    for name in ('control_manifest', 'control_archive'):
        record = chain[name]
        if file_sha(record['path']) != record['sha256']:
            raise ValueError('Carried kernel control file changed: '+name)
    if chain['control_manifest']['sha256'] != audit['baseline_manifest_sha256']:
        raise ValueError('Carried kernel control manifest mismatch')
    control_heads = heads_from_manifest(Path(chain['control_manifest']['path']).read_bytes())
    if control_heads != control['source_heads']:
        raise ValueError('Carried kernel control source mismatch')
    if (parent['source_heads'] != audit['source_heads'] or
        any(control_heads[p] != frozen[p] or parent['source_heads'][p] != frozen[p] for p in CONTRACT) or
        parent['normalized_config_sha256'] != audit['normalized_config_sha256']):
        raise ValueError('Only an unchanged kernel/prebuilt/vendor/config contract can be carried')
    if (control.get('candidate_evidence', {}).get('kernel_audit', {}).get('sha256') != chain['audit']['sha256'] or
        control['archive_sha256'] != chain['control_archive']['sha256'] or
        control.get('historical', {}).get('musthold') != 'pass' or
        not control['historical'].get('checks') or not all(c.get('pass') is True for c in control['historical']['checks']) or
        len(control.get('supplemental', [])) != 7 or {r['coverage'] for r in control.get('supplemental', [])} !=
        {'policy','patch_packaging','private_compatibility','health_semantics','gms_themes_apps','doze_packaging','install_integrity'} or
        any(r.get('exit') != 0 for r in control['supplemental'])):
        raise ValueError('Carried kernel requires its verified control archive and exact audited contract')
    parent_check(parent)
    evidence = control.get('kernel_artifact_evidence', {})
    if set(evidence) != {'kernel-artifact-binding.json','image-files.json','filesystem-files.json'}:
        raise ValueError('Carried kernel control lacks packaged artifact binding evidence')
    reports = {name:load(dict(path=str(Path(chain['control_results']['path']).parent/name),sha256=digest))
               for name,digest in evidence.items()}
    artifact_check(reports['kernel-artifact-binding.json'], parent, control_heads, control['archive_sha256'],
                   reports['image-files.json'], reports['filesystem-files.json'])


def carry(origin, results, control_manifest, control_archive, frozen, heads_from_manifest):
    parent = candidate_gates.revalidate(origin)
    control = candidate_gates.revalidate(results)
    baseline_heads = heads_from_manifest(Path(control_manifest['path']).read_bytes())
    if set(baseline_heads) != set(frozen) or any(baseline_heads[p] != frozen[p] for p in frozen if p != kernel_contract.DEVICE):
        raise ValueError('Kernel carry stage may change only the device project over its control')
    audit = copy.deepcopy(parent)
    audit['baseline_manifest_sha256'] = control_manifest['sha256']
    audit['kernel_carry'] = dict(audit=origin, control_results=results, control_manifest=control_manifest,
                                control_archive=control_archive)
    candidate_gates.validate_audit(audit, frozen, control_manifest['sha256'])
    return audit


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--control-results', type=Path, required=True)
    ap.add_argument('--control-manifest', type=Path, required=True)
    ap.add_argument('--control-archive', type=Path, required=True)
    ap.add_argument('--candidate-manifest', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    import controller
    import paths
    if not args.output.resolve().is_relative_to(paths.DIAGNOSTICS.resolve()):
        raise ValueError('Carried audit must be preserved in diagnostics/builds')
    results = json.loads(args.control_results.read_text())
    heads = lambda data: controller.expected_heads(controller.manifest_heads(data))
    frozen = heads(args.candidate_manifest.read_bytes())
    audit = carry(results['candidate_evidence']['kernel_audit'], candidate_gates.file_record(args.control_results),
                  candidate_gates.file_record(args.control_manifest), candidate_gates.file_record(args.control_archive),
                  frozen, heads)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as out:
        json.dump(audit, out, indent=2)
    print(args.output)


if __name__ == '__main__':
    main()
