#!/usr/bin/env python3
"""Positive semantic signoff tied to the reviewed source HEAD, not commit subjects."""
import json,os,subprocess,sys
from pathlib import Path
ready=json.loads(Path(os.environ['EVOX_READY']).read_text())
project,purpose=sys.argv[1:]
head=subprocess.check_output(['git','-C','/mnt/wsl/evox/src/'+project,'rev-parse','HEAD'],text=True).strip()
matches=[c for c in ready.get('semantic_checks',[]) if c.get('project')==project and c.get('purpose')==purpose]
if len(matches)!=1 or matches[0].get('pass') is not True or matches[0].get('head')!=head or not matches[0].get('evidence'):
    raise SystemExit('Missing/mismatched semantic source review: '+project+': '+purpose)
