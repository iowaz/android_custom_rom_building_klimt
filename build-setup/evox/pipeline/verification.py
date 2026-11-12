"""Verification mode record: resolution at readiness, widening at recheck, and the promotion contract.

`simple` checks the artifact, staging and delivery; `full` is the established verifier. ready.py resolves the
mode once from recorded inputs (this build's readiness against the last promoted build's) and seals it in
BUILD_READY.json under `verification`. A readiness without that record is verified as full (legacy path).
See docs/designs/verifier-simplification.md. Pure functions here; no I/O except in the callers.
"""
import re

SCHEMA = 1
MODES = ('simple', 'full')
TRACKS = ('policy', 'patch_packaging', 'private_compatibility', 'health_semantics', 'gms_themes_apps',
          'doze_packaging', 'install_integrity')
EXTRAS = TRACKS + ('kernel',)
SIMPLE_CHECKS = ('attempt.provenance', 'archive.integrity', 'avb.chain', 'flash.layout', 'dtb.live',
                 'identity.metadata', 'staging.clean', 'signing.platform')
CANDIDATE_CHECKS = ('candidate.kernel_binding', 'candidate.rollback_security')

KERNEL_PROJECTS = ('kernel/xiaomi/klimt', 'kernel/xiaomi/klimt-prebuilt')
# Recorded project heads whose change is never routine.
FULL_PROJECTS = ('vendor/xiaomi/klimt',)
# Unpatched projects whose change selects a focused track.
PROJECT_EXTRAS = {
    'hardware/xiaomi': 'private_compatibility',
    'device/mediatek/sepolicy_vndr': 'policy',
    'vendor/gms': 'gms_themes_apps',
    'vendor/gms-mosey': 'gms_themes_apps',
}
# Projects that carry a class `klimt` device patch, by the track that checks that patch's effect. A changed
# upstream base or patch content selects the track. Class `personal` patches are the identity layer, which
# identity.metadata checks on every build.
PATCHED_PROJECT_EXTRAS = {
    'device/lineage/sepolicy': 'policy',
    'build/soong': 'patch_packaging',
    'frameworks/native': 'patch_packaging',
    'hardware/interfaces': 'patch_packaging',
}
# Device-tree paths (git diff --name-only between the two device heads). First match wins; None = no extra.
DEVICE_PATHS = [
    (r'patches/', None),               # covered by the patch-bundle comparison
    (r'sepolicy/', 'policy'),
    (r'miui-stub/', 'patch_packaging'),
    (r'wifi/', 'private_compatibility'),
    (r'proprietary-files\.txt$', 'private_compatibility'),
    (r'health/', 'health_semantics'),
    (r'(udfps|parts|apps|overlay|overlay-product|rro_overlays)/', 'doze_packaging'),
    (r'modules\.load\.', 'full'),
    (r'rootdir/.*fstab', 'full'),
    (r'libinit/', None),
]
BOARD_FULL = re.compile(r'^[+-](?![+-]).*\b(BOARD_\w*PARTITION\w*|BOARD_SUPER_\w*|BOARD_AVB_\w*)')


class Defect(Exception):
    """An artifact or assertion defect: exit 1."""
    def __init__(self, message, check=None):
        super().__init__(message)
        self.check = check


class Missing(Exception):
    """Missing/unsupported tool or evidence, or the wrong host: exit 2."""
    def __init__(self, message, check=None):
        super().__init__(message)
        self.check = check


def exit_code(error):
    import subprocess as sp
    if isinstance(error, KeyboardInterrupt):
        return 130
    if isinstance(error, Defect):
        return 1
    if isinstance(error, Missing):
        return 2
    if isinstance(error, sp.CalledProcessError):
        return error.returncode if error.returncode in (1, 2) else 3
    if isinstance(error, (RuntimeError, FileNotFoundError, KeyError)):
        return 2  # legacy preconditions: drift, missing records or evidence
    return 3


def mode_of(ready):
    record = ready.get('verification')
    return record['mode'] if record else 'full'


def validate_record(record):
    if not isinstance(record, dict) or record.get('schema') != SCHEMA or record.get('mode') not in MODES:
        raise ValueError('verification record: schema/mode invalid')
    extras = record.get('extras')
    if not isinstance(extras, list) or extras != sorted(set(extras)) or any(e not in EXTRAS for e in extras):
        raise ValueError('verification record: extras must be sorted, unique, known')
    if record['mode'] == 'full' and extras:
        raise ValueError('verification record: full mode has no extras')
    if not isinstance(record.get('candidate'), bool) or not isinstance(record.get('reasons'), list):
        raise ValueError('verification record: candidate/reasons invalid')
    if record['candidate'] and record['mode'] == 'simple' and 'kernel' not in extras:
        raise ValueError('verification record: a simple candidate needs the kernel extra')
    if record['mode'] == 'simple':
        baseline = record.get('baseline')
        if not isinstance(baseline, dict) or not baseline.get('build') or not baseline.get('avb_keys'):
            raise ValueError('verification record: simple mode needs a baseline with AVB keys')
    return record


def required_checks(record):
    """Exact check IDs a simple run must report; None for full (legacy contract)."""
    validate_record(record)
    if record['mode'] == 'full':
        return None
    ids = list(SIMPLE_CHECKS)
    ids += ['track.' + t for t in TRACKS if t in record['extras']]
    if 'kernel' in record['extras']:
        ids.append('kernel.modules')
    if record['candidate']:
        ids += list(CANDIDATE_CHECKS)
    return ids


def _patch_differs(old, new):
    return old is None or new is None or any(old.get(k) != new.get(k) for k in ('base', 'final_head', 'final_tree', 'class'))


def computed(current, baseline, device_paths, board_diff, kernel_baseline):
    """(mode, extras, candidate, reasons) from this readiness against the baseline's. Never removes a need."""
    reasons, extras, full = [], set(), False
    heads = current['reviewed_project_heads']
    candidate = heads.get(KERNEL_PROJECTS[0]) != kernel_baseline
    if candidate:
        extras.add('kernel')
        reasons.append('kernel head differs from kernel_contract.BASELINE: candidate add-on')
    if baseline is None:
        return 'full', [], candidate, reasons + ['no promoted baseline build with a readable BUILD_READY.json']
    old = baseline['reviewed_project_heads']
    name = baseline.get('build', 'baseline')
    for key, label in (('target', 'target'), ('public_certificate_sha256', 'public signing certificates')):
        if current.get(key) != baseline.get(key):
            full = True
            reasons.append(f'{label} changed since {name}')
    for project in FULL_PROJECTS:
        if heads.get(project) != old.get(project):
            full = True
            reasons.append(f'{project} changed since {name}')
    for project in KERNEL_PROJECTS:
        if heads.get(project) != old.get(project):
            extras.add('kernel')
            reasons.append(f'{project} changed since {name}')
    for project, extra in PROJECT_EXTRAS.items():
        if heads.get(project) != old.get(project):
            extras.add(extra)
            reasons.append(f'{project} changed since {name}: {extra}')
    new_bundle = current.get('patch_bundle', {}).get('projects', {})
    old_bundle = baseline.get('patch_bundle', {}).get('projects', {})
    for project in sorted(set(new_bundle) | set(old_bundle)):
        if not _patch_differs(old_bundle.get(project), new_bundle.get(project)):
            continue
        record = new_bundle.get(project) or old_bundle.get(project)
        extra = PATCHED_PROJECT_EXTRAS.get(project)
        if extra:
            extras.add(extra)
            reasons.append(f'patched {project} (base or patch) changed since {name}: {extra}')
        elif record.get('class') == 'personal':
            reasons.append(f'personal patch {project} changed since {name}: identity.metadata (always run)')
        else:
            full = True
            reasons.append(f'klimt patch on unmapped project {project} changed since {name}')
    if device_paths is None:
        full = True
        reasons.append('device tree change list unavailable')
    else:
        for path in device_paths:
            if path == 'BoardConfig.mk':
                if any(BOARD_FULL.match(line) for line in (board_diff or '').splitlines()):
                    full = True
                    reasons.append('BoardConfig.mk partition/super/AVB lines changed since ' + name)
                continue
            for pattern, extra in DEVICE_PATHS:
                if re.match(pattern, path):
                    if extra == 'full':
                        full = True
                        reasons.append(f'device tree {path} changed since {name}')
                    elif extra:
                        extras.add(extra)
                        reasons.append(f'device tree {path} changed since {name}: {extra}')
                    break
    if full:
        return 'full', [], candidate, reasons
    return 'simple', sorted(extras), candidate, reasons


def resolve(current, baseline, device_paths, board_diff, kernel_baseline, request, baseline_identity):
    """The sealed record. request: dict(mode=None|'simple'|'full', extras=[...], reason=str|None)."""
    mode, extras, candidate, reasons = computed(current, baseline, device_paths, board_diff, kernel_baseline)
    asked = request.get('mode')
    wanted = list(request.get('extras') or [])
    unknown = [e for e in wanted if e not in EXTRAS]
    if asked not in (None, *MODES) or unknown:
        raise ValueError(f'Unknown mode/extra: {asked} {unknown}; extras are {", ".join(EXTRAS)}')
    if asked == 'simple' and mode == 'full':
        raise ValueError('Simple mode refused; recorded inputs require full: ' + '; '.join(reasons))
    if asked == 'full' and mode != 'full':
        mode = 'full'
        reasons.append('operator selected full')
    if mode == 'simple' and wanted:
        extras = sorted(set(extras) | set(wanted))
        reasons.append('operator added ' + ', '.join(sorted(wanted)))
    if mode == 'full':
        extras = []
    record = dict(schema=SCHEMA, mode=mode, extras=extras, candidate=candidate, reasons=reasons,
                  request=dict(mode=asked, extras=sorted(wanted), reason=request.get('reason')),
                  baseline=baseline_identity)
    return validate_record(record)


def widen(original, review):
    """A recheck may add extras or select full, never remove what the sealed readiness selected."""
    if review is None:
        return original
    validate_record(review)
    if original is None:
        if review['mode'] != 'full':
            raise ValueError('A legacy readiness is verified in full; a recheck cannot select simple')
        return review
    validate_record(original)
    if review['candidate'] != original['candidate'] or review.get('baseline') != original.get('baseline'):
        raise ValueError('A recheck cannot change the candidate state or the baseline')
    if review['mode'] == 'simple' and (original['mode'] == 'full' or not set(original['extras']) <= set(review['extras'])):
        raise ValueError('A recheck cannot remove checks the sealed readiness selected')
    return review


def effective_record(ready, review):
    return widen(ready.get('verification'), (review or {}).get('verification'))


def check_results(record, results):
    """Promotion contract for a schema-2 report: the sealed record and exactly its passing checks."""
    required = required_checks(record)
    if required is None:
        raise ValueError('A full verification record is promoted through the legacy report contract')
    if results.get('schema') != 2 or results.get('verification') != record:
        raise ValueError('Report verification record differs from the sealed readiness/recheck record')
    checks = results.get('checks')
    ids = [c.get('id') for c in checks] if isinstance(checks, list) else None
    if ids != required:
        raise ValueError(f'Report checks differ from the required list: {ids} != {required}')
    failed = [c['id'] for c in checks if c.get('outcome') != 'pass']
    if failed:
        raise ValueError('Required checks did not pass: ' + ', '.join(failed))
    if results.get('runtime_unvalidated') is not True:
        raise ValueError('runtime_unvalidated must be true')
    return required


def vbmeta_keys(info_text):
    """{'vbmeta': sha1, <chained partition>: sha1} from `avbtool info_image --image vbmeta.img`."""
    own = re.search(r'^Public key \(sha1\):\s*([0-9a-f]{40})\s*$', info_text, re.M)
    if not own:
        raise ValueError('vbmeta.img has no public key')
    keys = {'vbmeta': own[1]}
    for block in info_text.split('    Chain Partition descriptor:')[1:]:
        part = re.search(r'^      Partition Name:\s*(\S+)', block, re.M)
        key = re.search(r'^      Public key \(sha1\):\s*([0-9a-f]{40})', block, re.M)
        if not part or not key or part[1] in keys:
            raise ValueError('Malformed or duplicate AVB chain descriptor')
        keys[part[1]] = key[1]
    return keys


def build_order(name):
    """Sort key for build names: evoxNN before every date build; 20261105 < 20261105.2 < 20261105.10."""
    m = re.fullmatch(r'evox(\d+)', name)
    if m:
        return (0, int(m[1]), 0)
    m = re.fullmatch(r'(\d{8})(?:\.(\d+))?', name)
    if not m:
        raise ValueError('Not a build name: ' + name)
    return (1, int(m[1]), int(m[2] or 1))
