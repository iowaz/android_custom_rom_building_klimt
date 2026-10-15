"""Publish local commits from a SHALLOW checkout to a GitHub fork via the Git Data API.

Shallow repos can't negotiate a small push, so each commit in base..HEAD is
recreated server-side (changed blobs -> tree on the parent tree -> commit with
the original author/committer/dates/message). The branch is created/updated only
when GitHub's commit SHA equals the local SHA, proving byte-identical history.
usage: gh_replay_commits.py <local repo> <owner/repo> <base sha> <branch>
"""
import base64, json, os, subprocess as sp, sys, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone

repo, slug, base, branch = sys.argv[1:5]
TOKEN = os.environ['GH_TOKEN']
def api(method, path, body=None):
    req = urllib.request.Request('https://api.github.com/repos/' + slug + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={'Authorization': 'Bearer ' + TOKEN, 'Accept': 'application/vnd.github+json'})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read() or b'null')
    except urllib.error.HTTPError as e:
        if method == 'GET' and e.code == 404:
            return None
        raise RuntimeError(f'{method} {path}: {e.code} {e.read()[:300]!r}')
def git(*a, binary=False):
    out = sp.run(['git', '-C', repo, *a], check=True, stdout=sp.PIPE).stdout
    return out if binary else out.decode()
def person(line):
    # "Name <email> 1792000000 -0300"
    name, rest = line.rsplit(' <', 1); email, rest = rest.split('> ', 1)
    ts, tz = rest.split(); sign = -1 if tz[0] == '-' else 1
    off = timedelta(hours=int(tz[1:3]), minutes=int(tz[3:5])) * sign
    return {'name': name, 'email': email, 'date': datetime.fromtimestamp(int(ts), timezone(off)).isoformat()}

assert api('GET', '/commits/' + base), 'base commit missing on fork'
commits = git('rev-list', '--reverse', base + '..HEAD').split()
for sha in commits:
    raw = git('cat-file', 'commit', sha)
    header, message = raw.split('\n\n', 1)
    fields = {}
    for l in header.splitlines():
        k, v = l.split(' ', 1); fields.setdefault(k, []).append(v)
    assert 'gpgsig' not in fields and len(fields['parent']) == 1, sha
    parent = fields['parent'][0]
    entries = []
    parts = git('diff-tree', '-r', '--no-renames', '--no-commit-id', '-z', parent, sha).split('\0')
    for meta, path in zip(parts[0:-1:2], parts[1::2]):
        _, newmode, _, newsha, status = meta.lstrip(':').split()
        if status == 'D':
            entries.append({'path': path, 'mode': '100644', 'type': 'blob', 'sha': None})
        elif newmode == '160000':
            entries.append({'path': path, 'mode': newmode, 'type': 'commit', 'sha': newsha})
        else:
            if not api('GET', '/git/blobs/' + newsha):
                data = git('cat-file', 'blob', newsha, binary=True)
                got = api('POST', '/git/blobs', {'content': base64.b64encode(data).decode(), 'encoding': 'base64'})['sha']
                assert got == newsha, (path, got, newsha)
            entries.append({'path': path, 'mode': newmode, 'type': 'blob', 'sha': newsha})
    tree = api('POST', '/git/trees', {'base_tree': git('rev-parse', parent + '^{tree}').strip(), 'tree': entries})['sha']
    assert tree == fields['tree'][0], ('tree mismatch', sha, tree)
    made = api('POST', '/git/commits', {'message': message, 'tree': tree, 'parents': [parent],
                                         'author': person(fields['author'][0]), 'committer': person(fields['committer'][0])})['sha']
    if made != sha:
        raise SystemExit(f'COMMIT SHA MISMATCH {sha} -> {made}; branch NOT updated')
    print('replayed', sha[:12], git('log', '-1', '--format=%s', sha).strip(), flush=True)
head = commits[-1]
if api('GET', '/git/ref/heads/' + branch):
    api('PATCH', '/git/refs/heads/' + branch, {'sha': head, 'force': False})
else:
    api('POST', '/git/refs', {'ref': 'refs/heads/' + branch, 'sha': head})
print('OK', slug, branch, '->', head, flush=True)
