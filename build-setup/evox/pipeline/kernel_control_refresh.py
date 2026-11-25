"""Establish a fresh control for one upstream build from a fully verified delivered image."""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import sys

import candidate_gates as gates
import kernel_artifact
import kernel_carry
import paths
import rollback_security

MODE = 'verified-image-kernel-control-refresh'
REPORTS = {'kernel-artifact-binding.json', 'image-files.json', 'filesystem-files.json'}
COVERAGE = {'policy', 'patch_packaging', 'private_compatibility', 'health_semantics',
            'gms_themes_apps', 'doze_packaging', 'install_integrity'}


def validate(record, build, snapshot_sha, control_sha, frozen, tooling, load=None,
             heads=None, now=None, proof_check=None, binding_check=None, digest=None):
    load = load or gates.revalidate
    digest = digest or rollback_security.digest
    if heads is None:
        import controller
        heads = lambda raw: controller.expected_heads(controller.manifest_heads(raw))
    proof_check = proof_check or gates.validate_audit
    binding_check = binding_check or kernel_artifact.validate_receipt
    if (record.get('schema') != 1 or record.get('mode') != MODE or
            record.get('build') != build or record.get('snapshot_sha256') != snapshot_sha or
            record.get('control_manifest', {}).get('sha256') != control_sha or
            record.get('tooling_sha256') != tooling):
        raise ValueError('Fresh control is not bound to this build/source/tooling')
    gates.freeze_deadline({'control_freeze_utc': record['validated_utc']}, now)
    manifest = record['control_manifest']
    if digest(manifest['path']) != manifest['sha256']:
        raise ValueError('Fresh control manifest changed')
    control_heads = heads(Path(manifest['path']).read_bytes())
    kernel_carry.unchanged_contract(control_heads, frozen)
    results = load(record['control_results'])
    archived = record['control_archive']
    if digest(archived['path']) != archived['sha256']:
        raise ValueError('Fresh control archive changed')
    expected = json.loads((paths.PIPELINE / 'expected-legacy-checks.json').read_text())
    historical = results.get('historical', {})
    checks = historical.get('checks', [])
    tracks = results.get('supplemental', [])
    if (results.get('source_heads') != control_heads or results.get('archive_sha256') != archived['sha256'] or
            historical.get('musthold') != 'pass' or len(checks) != len(expected) or
            {c.get('name') for c in checks} != set(expected) or any(c.get('pass') is not True for c in checks) or
            len(tracks) != len(COVERAGE) or {c.get('coverage') for c in tracks} != COVERAGE or
            any(c.get('exit') != 0 for c in tracks)):
        raise ValueError('Fresh control requires a complete passing full image verification')
    produced = load(record['build_exit'])
    promoted = load(record['promotion'])
    if (produced.get('exit') != 0 or produced.get('zip_sha256') != archived['sha256'] or
            results.get('archive_bytes') != produced.get('zip_bytes') or
            promoted.get('archive_sha256') != archived['sha256'] or
            promoted.get('build') != record.get('control_build') or
            promoted.get('report') != str(Path(record['control_results']['path']).parent) or
            Path(archived['path']).parent != Path(promoted.get('delivery', ''))):
        raise ValueError('Fresh control is not the completed promoted producing artifact')
    audit_record = results['candidate_evidence']['kernel_audit']
    audit = load(audit_record)
    proof_check(audit, control_heads, audit['baseline_manifest_sha256'])
    reports = results.get('kernel_artifact_evidence', {})
    if set(reports) != REPORTS or set(record.get('reports', {})) != REPORTS:
        raise ValueError('Complete packaged kernel binding inventories required')
    loaded = {}
    for name in REPORTS:
        ref = record['reports'][name]
        if ref != dict(path=str(Path(record['control_results']['path']).parent / name), sha256=reports[name]):
            raise ValueError('Fresh control report binding mismatch')
        loaded[name] = load(ref)
    binding_check(loaded['kernel-artifact-binding.json'], audit, control_heads, archived['sha256'],
                  loaded['image-files.json'], loaded['filesystem-files.json'])
    fresh_binding = load(record['fresh_binding'])
    fresh_security = load(record['fresh_security'])
    verified_security = load(record['verified_security'])
    control_ready = load(record['control_ready'])
    if (fresh_binding != loaded['kernel-artifact-binding.json'] or
            fresh_security.get('baseline_manifest_sha256') != control_sha or
            fresh_security.get('verified_results') != record['control_results'] or
            fresh_security.get('archive') != archived or fresh_security.get('security') != verified_security or
            record['verified_security']['sha256'] != results.get('rollback_security', {}).get('rollback-security-candidate.json') or
            record.get('certificates') != control_ready.get('public_certificate_sha256') or
            control_ready.get('effective_project_heads') != control_heads):
        raise ValueError('Fresh control kernel/security/certificate recapture failed')
    for name, certificate in record['certificates'].items():
        if digest(paths.SRC / 'vendor/evolution-priv/keys' / (name + '.x509.pem')) != certificate:
            raise ValueError('Fresh control signing certificates changed')
    return record


def main():
    import hostcheck
    hostcheck.require_linux(__file__)
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('build')
    ap.add_argument('--control', required=True)
    ap.add_argument('--control-extract', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    args = ap.parse_args()
    import controller
    if not paths.is_build(args.build) or not paths.is_build(args.control):
        raise ValueError('Valid date-named build/control required')
    if not args.output.resolve().is_relative_to(paths.for_build(args.build)['debug'].resolve()):
        raise ValueError('Fresh control evidence must be preserved under this build diagnostics')
    snapshot = paths.SNAPSHOTS / (args.build + '.xml')
    baseline = paths.SNAPSHOTS / (args.control + '.xml')
    frozen = controller.expected_heads(controller.manifest_heads(snapshot.read_bytes()))
    control_debug = paths.for_build(args.control)['debug']
    promotion_path = control_debug / 'PROMOTED.json'
    promotion = json.loads(promotion_path.read_text())
    report = Path(promotion['report'])
    results_path = report / 'RESULTS.json'
    results = json.loads(results_path.read_text())
    archive = Path(promotion['delivery']) / ('lineage_klimt-' + args.control + '-img.zip')
    control_heads = controller.expected_heads(controller.manifest_heads(baseline.read_bytes()))
    audit = gates.revalidate(results['candidate_evidence']['kernel_audit'])
    with controller.lock(paths.for_build(args.build)['logs'] / 'source.lock'), controller.lock(paths.for_build(args.build)['logs'] / 'verification.lock'):
        if controller.foreign_processes():
            raise ValueError('Build or extraction active')
        args.output.mkdir(parents=True, exist_ok=False)
        tooling = controller.tooling_hashes()
        controller.live_heads(frozen)
        kernel_carry.unchanged_contract(control_heads, frozen)
        print('Revalidating complete audited kernel proofs and delivered control image', flush=True)
        gates.validate_audit(audit, control_heads, audit['baseline_manifest_sha256'])
        security = args.output / 'control-security.json'
        subprocess.run([sys.executable, '-B', str(paths.PIPELINE / 'capture_security_control.py'),
            '--snapshot', str(baseline), '--extract', str(args.control_extract), '--archive', str(archive),
            '--report', str(report), '--output', str(security)], check=True)
        print('Rebinding the control image kernel/modules to audited ELFs', flush=True)
        binding = kernel_artifact.validate(audit, control_heads, args.control_extract / 'img/boot.img',
            args.control_extract / 'fs/system_dlkm', results['archive_sha256'], paths.SRC)
        binding_path = args.output / 'kernel-binding.json'
        controller.write_json(binding_path, binding, True)
        ready_path = control_debug / 'BUILD_READY.json'
        ready = json.loads(ready_path.read_text())
        record = dict(schema=1, mode=MODE, build=args.build, control_build=args.control,
            snapshot_sha256=controller.sha(snapshot), control_manifest=gates.file_record(baseline),
            control_results=gates.file_record(results_path), control_archive=gates.file_record(archive),
            promotion=gates.file_record(promotion_path), control_ready=gates.file_record(ready_path),
            build_exit=gates.file_record(paths.for_build(args.control)['logs'] / promotion['attempt'] / 'build-exit.json'),
            reports={name:gates.file_record(report / name) for name in REPORTS},
            fresh_binding=gates.file_record(binding_path), fresh_security=gates.file_record(security),
            verified_security=gates.file_record(report / 'rollback-security-candidate.json'),
            certificates=ready['public_certificate_sha256'], tooling_sha256=tooling,
            validated_utc=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
        validate(record, args.build, controller.sha(snapshot), controller.sha(baseline), frozen, tooling)
        controller.live_heads(frozen)
        if tooling != controller.tooling_hashes():
            raise ValueError('Fresh control tooling changed')
        output = args.output / 'CONTROL_REFRESH.json'
        controller.write_json(output, record, True)
        print(output, flush=True)


if __name__ == '__main__':
    main()
