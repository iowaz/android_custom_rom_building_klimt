#!/usr/bin/env python3
"""Compare the complete retained kernel/module type contract in isolated build outputs."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def elf_symbols(text):
    result = {}
    block = None
    for line in text.splitlines():
        if line == 'elf_symbol {':
            block = {}
        elif block is not None:
            if line == '}':
                if 'name' in block:
                    result[block['name']] = block
                block = None
            elif line.startswith('  name: '):
                block['name'] = json.loads(line.partition(': ')[2])
            elif line.startswith('  type_id: '):
                block['type_id'] = line.partition(': ')[2]
    return result


def require_coverage(text, expected):
    symbols = elf_symbols(text)
    missing = sorted(set(expected)-set(symbols))
    untyped = sorted(s for s in set(expected)&set(symbols) if 'type_id' not in symbols[s])
    if missing or not expected:
        raise ValueError('Incomplete ABI graph: missing='+str(missing[:30])+' untyped='+str(untyped[:30]))
    return dict(symbols=len(set(expected)), untyped=untyped)


def extract(tool, obj, symbols, output):
    obj, output = Path(obj), Path(output)
    symvers = {l.split()[1] for l in (obj/'Module.symvers').read_text().splitlines()}
    expected = set(symbols)&symvers
    filters = output.with_suffix('.symbols')
    filters.write_text('[abi_symbol_list]\n'+'\n'.join(sorted(symbols))+'\n')
    inputs = [obj/'vmlinux', *sorted(obj.rglob('*.ko'))]
    argv = [str(tool), '-e', *map(str,inputs), '-S', ':'+str(filters), '-o', str(output)]
    with output.with_suffix('.log').open('w') as log:
        subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT, check=True)
    coverage = require_coverage(output.read_text(), expected)
    def sha(p):
        return hashlib.sha256(p.read_bytes()).hexdigest()
    record = dict(argv=argv, **coverage, tool_sha256=sha(Path(tool)),
                  inputs=[dict(path=str(p), sha256=sha(p)) for p in inputs], graph_sha256=sha(output))
    output.with_suffix('.inputs.json').write_text(json.dumps(record, indent=2))
    return record


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tool-directory', required=True, type=Path)
    ap.add_argument('--old', required=True, type=Path)
    ap.add_argument('--new', required=True, type=Path)
    ap.add_argument('--symbols', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    ap.add_argument('--declaration-review', type=Path, help='unchanged declaration/provider evidence for assembly exports without DWARF types')
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    symbols = set(args.symbols.read_text().split())
    records = {name:extract(args.tool_directory/'stg', obj, symbols, args.output/(name+'.stg'))
               for name,obj in [('old',args.old), ('new',args.new)]}
    result = subprocess.run([str(args.tool_directory/'stgdiff'), '-s', str(args.output/'old.stg'),
                             '-s', str(args.output/'new.stg'), '-f', 'small', '-o', str(args.output/'type-diff.txt')])
    untyped = records['old']['untyped']
    if untyped or records['new']['untyped']:
        if not args.declaration_review:
            raise ValueError('Assembly exports require explicit unchanged declaration/provider review: '+str(untyped))
        review = json.loads(args.declaration_review.read_text())
        if review.get('pass') is not True or set(review.get('symbols', {})) != set(untyped) or untyped != records['new']['untyped']:
            raise ValueError('Assembly declaration review incomplete/mismatched')
        for item in review['symbols'].values():
            if not item.get('declarations') or not item.get('providers') or not item.get('explanation'):
                raise ValueError('Assembly declaration/provider evidence absent')
            for proof in item['declarations']+item['providers']:
                old = Path(proof['old']).read_bytes(); new = Path(proof['new']).read_bytes()
                if old != new or hashlib.sha256(old).hexdigest() != proof['sha256']:
                    raise ValueError('Assembly declaration/provider is changed or proof hash drifted')
    (args.output/'RESULT.json').write_text(json.dumps(dict(exit=result.returncode, **{'pass':result.returncode==0}, inputs=records,
                                                         declaration_review=str(args.declaration_review)), indent=2))
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
