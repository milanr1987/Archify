"""Rebuild and verify the local demo using the installed Archify and Chromium."""
import json
import os
import subprocess
import shutil
from pathlib import Path

from atlas.cli import main

root = Path(__file__).resolve().parents[1]
import prepare_map_demo  # prepares explicit local config and source evidence

analysis = json.loads((root/'data/demo-input/analysis.json').read_text(encoding='utf-8'))
code = main(['map',analysis['projectId'],'--analysis','data/demo-input/analysis.json',
             '--input','data/demo-input/native.json','--slug','atlas-demo','--type','workflow'])
if code:
    raise SystemExit(code)
env = dict(os.environ,ARCHIFY_UPDATE_CHECK_DISABLED='1')
chromes = sorted((root/'.playwright-browsers').glob('chromium-*/chrome-win64/chrome.exe'))
if chromes and 'ARCHIFY_CHROME' not in env:
    env['ARCHIFY_CHROME'] = str(chromes[-1])
bundled_node = root/'.venv/Lib/site-packages/playwright/driver/node.exe'
node = str(bundled_node) if bundled_node.exists() else shutil.which('node')
if not node:
    raise SystemExit('Za mapu instaliraj Node.js 18+ ili setup -Development.')
result = subprocess.run([node,
    str(root/'vendor/archify/archify/bin/archify.mjs'),'finalize','workflow',
    'data/maps/atlas-demo.json','output/maps/atlas-demo.html','--quality','standard','--json'],
    cwd=root,env=env,timeout=120)
raise SystemExit(result.returncode)
