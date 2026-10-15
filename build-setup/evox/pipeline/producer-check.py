#!/usr/bin/env python3
import hashlib,os,sys
from pathlib import Path
S=Path('/mnt/wsl/evox/src')
F=Path(os.environ['EVOX_EXTRACT'])/'fs'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
if sys.argv[1]=='runtime-apex':
    candidates=list((F/'system/system/apex').glob('com.android.runtime.*apex'))
    if len(candidates)!=1:raise SystemExit('Runtime APEX missing/ambiguous')
    built=S/'out/target/product/klimt/system/apex'/candidates[0].name
    if not built.is_file() or sha(built)!=sha(candidates[0]):raise SystemExit('Runtime APEX differs from current installed producer')
else:raise SystemExit('Unknown producer check')
