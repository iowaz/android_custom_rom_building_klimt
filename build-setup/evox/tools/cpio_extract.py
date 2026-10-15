#!/usr/bin/env python3
# Minimal newc (070701) cpio extractor: regular files and dirs only. Usage: cpio_extract.py <archive> <outdir>
import os, sys
d = open(sys.argv[1], 'rb').read(); out = sys.argv[2]; p = 0; n = 0
while p + 110 <= len(d):
    if d[p:p+6] not in (b'070701', b'070702'):
        nx = d.find(b'07070', p + 1)
        if nx < 0: break
        p = nx; continue
    h = d[p:p+110]
    f = lambda i: int(h[6+i*8:14+i*8], 16)
    mode, fsize, nsize = f(1), f(6), f(11)
    name = d[p+110:p+110+nsize-1].decode(errors='replace')
    q = (p + 110 + nsize + 3) & ~3
    data = d[q:q+fsize]; p = (q + fsize + 3) & ~3
    if name == 'TRAILER!!!':
        continue
    dst = os.path.join(out, name.lstrip('/'))
    t = mode & 0o170000
    if t == 0o040000:
        os.makedirs(dst, exist_ok=True)
    elif t == 0o100000:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, 'wb').write(data); n += 1
print(f"{sys.argv[1]}: {n} files")
