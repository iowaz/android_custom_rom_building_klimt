"""Fresh, artifact-bound control revalidation for an expired verifier-only recheck."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import candidate_gates as gates
import kernel_artifact
import paths
import rollback_security

MODE = 'unchanged-kernel-control-revalidation'


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def audit_identity(audit):
    return canonical({k: v for k, v in audit.items() if k != 'control_revalidation'})


def validate(record, ready, prep, audit, load=None, now=None, tooling=None):
    """A new dated receipt does not replace any original preparation or kernel proof."""
    load = load or gates.revalidate
    if tooling is None:
        import controller
        tooling = controller.tooling_hashes()
    if (record.get('schema') != 1 or record.get('mode') != MODE or
            ready.get('verification_only') is not True or record.get('build') != ready['build'] or
            record.get('attempt') != ready.get('verification_attempt') or
            record.get('preparation') != ready['candidate_evidence']['preparation'] or
            record.get('snapshot_sha256') != ready['sha256'] or
            record.get('heads_sha256') != canonical(ready['reviewed_project_heads']) or
            record.get('admission_tooling') != ready['tooling_sha256'] or
            record.get('tooling_sha256') != tooling or
            record.get('audit_sha256') != audit_identity(audit) or
            record.get('baseline_sha256') != prep['baseline_sha256'] or
            record.get('original_freeze_utc') != prep['control_freeze_utc'] or
            record.get('certificates') != ready['public_certificate_sha256']):
        raise ValueError('Control revalidation is not bound to this verification-only source/audit')
    stamp = record['validated_utc']
    gates.freeze_deadline({'control_freeze_utc': stamp}, now)
    if stamp <= prep['control_freeze_utc']:
        raise ValueError('Control revalidation must follow the original freeze')
    chain = audit.get('kernel_carry', {})
    if record.get('verified_control') != chain:
        raise ValueError('Control revalidation cannot change the fully verified control')
    build_exit = load(record['build_exit'])
    if (build_exit.get('exit') != 0 or record.get('archive_sha256') != build_exit.get('zip_sha256') or
            record.get('archive_bytes') != build_exit.get('zip_bytes') or
            record.get('attempt') != Path(record['build_exit']['path']).parent.name):
        raise ValueError('Control revalidation lacks the producing attempt identity')
    control = load(chain['control_results'])
    fresh = load(record['fresh_security'])
    original = load(ready['candidate_evidence']['rollback_baseline'])
    binding = load(record['fresh_kernel_binding'])
    review = load(record['security_review'])
    binding_name = 'kernel-artifact-binding.json'
    archived = load(dict(path=str(Path(chain['control_results']['path']).parent / binding_name),
                         sha256=control['kernel_artifact_evidence'][binding_name]))
    control_ready = load(record['control_ready'])
    if (fresh.get('baseline_manifest_sha256') != prep['baseline_sha256'] or
            fresh.get('verified_results') != chain['control_results'] or
            fresh.get('archive', {}).get('sha256') != chain['control_archive']['sha256'] or
            fresh.get('security') != original.get('security') or
            fresh['security']['actual_source_spl'] != ready['security']['platform_security_patch'] or
            binding != archived or binding.get('pass') is not True or
            control_ready.get('public_certificate_sha256') != record['certificates'] or
            control_ready.get('effective_project_heads') != control.get('source_heads') or
            review.get('pass') is not True or review.get('source_spl') != fresh['security']['actual_source_spl'] or
            review.get('certificates') != record['certificates'] or
            review.get('bulletin', {}).get('state') not in ('merged', 'in review', 'not started')):
        raise ValueError('Fresh kernel/SPL/rollback/certificate control revalidation failed')
    return record


def main():
    import hostcheck
    hostcheck.require_linux(__file__)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('attempt')
    parser.add_argument('--kernel-audit', required=True, type=Path)
    parser.add_argument('--control-extract', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    import controller
    import ready as readiness
    attempt = controller.L / args.attempt
    original = json.loads((attempt / 'BUILD_READY.json').read_text())
    frozen = original['reviewed_project_heads']
    evidence = original['candidate_evidence']
    prep = gates.revalidate(evidence['preparation'])
    audit = json.loads(args.kernel_audit.read_text())
    if audit.get('control_revalidation') or not args.output.resolve().is_relative_to(paths.DIAGNOSTICS.resolve()):
        raise ValueError('Use an unmodified release audit and a fresh diagnostics folder')
    with controller.lock(controller.L / 'source.lock'), controller.lock(controller.L / 'verification.lock'):
        if controller.foreign_processes():
            raise ValueError('Build or extraction is active')
        args.output.mkdir(parents=True, exist_ok=False)
        tooling = controller.tooling_hashes()
        controller.live_heads(controller.ready_heads(original))
        produced = json.loads((attempt / 'build-exit.json').read_text())
        if (produced['exit'] != 0 or controller.sha(paths.ZIP) != produced['zip_sha256'] or
                paths.ZIP.stat().st_size != produced['zip_bytes'] or
                paths.ZIP.stat().st_mtime_ns != produced['zip_mtime_ns']):
            raise ValueError('Producing archive changed')
        print('Revalidating the complete kernel proof and verified-control chain', flush=True)
        gates.validate_audit(audit, frozen, prep['baseline_sha256'])
        chain = audit['kernel_carry']
        control = gates.revalidate(chain['control_results'])
        control_audit = gates.revalidate(chain['audit'])
        report = Path(chain['control_results']['path']).parent
        print('Recapturing control security from its verified image inventories', flush=True)
        security = args.output / 'control-security-fresh.json'
        subprocess.run([sys.executable, '-B', str(paths.PIPELINE / 'capture_security_control.py'),
            '--snapshot', chain['control_manifest']['path'], '--extract', str(args.control_extract),
            '--archive', chain['control_archive']['path'], '--report', str(report), '--output', str(security)], check=True)
        print('Rebinding control kernel and module bytes to audited ELFs', flush=True)
        binding = kernel_artifact.validate(control_audit, control['source_heads'],
            args.control_extract / 'img/boot.img', args.control_extract / 'fs/system_dlkm',
            chain['control_archive']['sha256'], paths.SRC)
        binding_path = args.output / 'control-kernel-binding-fresh.json'
        controller.write_json(binding_path, binding, True)
        source_spl = readiness.security_patch_level(frozen)['platform_security_patch']
        certs = {n: controller.sha(paths.SRC / 'vendor/evolution-priv/keys' / (n + '.x509.pem'))
                 for n in readiness.CERTS}
        security_review = args.output / 'security-review.json'
        controller.write_json(security_review, {'pass': True, 'source_spl': source_spl, 'certificates': certs,
            'bulletin': readiness.bulletin_state(datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m'))}, True)
        control_build = chain['control_manifest']['path'].split('/')[-1].removesuffix('.xml')
        control_ready = paths.for_build(control_build)['debug'] / 'BUILD_READY.json'
        record = dict(schema=1, mode=MODE, build=original['build'], attempt=args.attempt,
            preparation=evidence['preparation'], snapshot_sha256=original['sha256'], heads_sha256=canonical(frozen),
            admission_tooling=original['tooling_sha256'], tooling_sha256=tooling, audit_sha256=audit_identity(audit),
            baseline_sha256=prep['baseline_sha256'], original_freeze_utc=prep['control_freeze_utc'],
            verified_control=chain, certificates=certs, build_exit=gates.file_record(attempt / 'build-exit.json'),
            archive_sha256=produced['zip_sha256'], archive_bytes=produced['zip_bytes'],
            fresh_security=gates.file_record(security), fresh_kernel_binding=gates.file_record(binding_path),
            security_review=gates.file_record(security_review), control_ready=gates.file_record(control_ready),
            validated_utc=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
        effective = dict(original, verification_only=True, verification_attempt=args.attempt)
        validate(record, effective, prep, audit)
        controller.live_heads(controller.ready_heads(original))
        if tooling != controller.tooling_hashes():
            raise ValueError('Revalidation tooling changed')
        receipt = args.output / 'CONTROL_REVALIDATION.json'
        controller.write_json(receipt, record, True)
        audit['control_revalidation'] = gates.file_record(receipt)
        result = args.output / 'kernel-audit-revalidated.json'
        controller.write_json(result, audit, True)
        print(result, flush=True)


if __name__ == '__main__':
    main()
