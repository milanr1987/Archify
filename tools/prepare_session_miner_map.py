"""Prepare and publish the session-miner workflow map from inspected source evidence.

Run from the Archify folder after `atlas refresh`; session-miner must be in the catalog.
Inputs go to data/session-miner-input/ (private, outside Git). Source files are only read.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from atlas.cli import main

root = Path(__file__).resolve().parents[1]
inv = json.loads((root/'data/inventory.json').read_text(encoding='utf-8'))
project = next((item for item in inv['items'] if item['kind'] == 'project' and item['name'] == 'session-miner'), None)
if project is None:
    raise SystemExit('session-miner nije u katalogu; dodaj ga u config i pokreni atlas refresh.')
project_root = Path(project['locations'][0]['path'])

# (id, naziv, svrha, fajl, tekst koji označava liniju, lane, kolona, tip čvora)
specs = [
    ('sessions', 'JSONL sesije', 'Claude Code i Codex sesije na disku; samo se čitaju',
     'src/sminer/snapshot.py', 'def copy_newer_jsonl', 'input', 0, 'external'),
    ('snapshot', 'Snapshot', 'Kopira nove JSONL fajlove u lokalnu arhivu',
     'src/sminer/snapshot.py', 'def copy_newer_jsonl', 'input', 1, 'backend'),
    ('ingest', 'Ingest', 'Parsira Claude i Codex format u Turn zapise',
     'src/sminer/cli.py', 'if args.command == "ingest":', 'input', 2, 'backend'),
    ('redaction', 'Redakcija', 'Uklanja ključeve, tokene i e-mailove; 200 znakova po turnu',
     'src/sminer/redaction.py', 'def redact', 'input', 3, 'security'),
    ('db', 'SQLite baza', 'Redaktovani turnovi i odluke u %LOCALAPPDATA%',
     'src/sminer/db.py', 'def insert_turns', 'input', 4, 'database'),
    ('detectors', 'Detektori', 'Korekcije, ponovljeni promptovi i tool petlje',
     'src/sminer/detectors.py', 'def detect_corrections', 'analysis', 1, 'backend'),
    ('metrics', 'Metrike', 'Baseline i poređenje sa trenutnim stanjem',
     'src/sminer/metrics.py', 'def compare', 'analysis', 2, 'backend'),
    ('report', 'Markdown izvještaj', 'Piše reports/latest.md za pregled',
     'src/sminer/report.py', 'def write_report', 'output', 2, 'frontend'),
    ('decide', 'Odluka', 'Bilježi ljudsku odluku; ništa ne primjenjuje',
     'src/sminer/db.py', 'def save_decision', 'output', 3, 'backend'),
    ('audit', 'Audit i draft-rule', 'Mjeri instrukcije i ispisuje diff; ne piše u ciljni fajl',
     'src/sminer/audit.py', 'def draft_rule_diff', 'output', 4, 'frontend'),
]
pairs = [('sessions', 'snapshot', 'kopija'), ('snapshot', 'ingest', 'JSONL'), ('ingest', 'redaction', 'tekst'),
         ('redaction', 'db', 'Turn'), ('db', 'detectors', 'load_turns'), ('detectors', 'metrics', 'kandidati'),
         ('detectors', 'report', 'nalazi'), ('metrics', 'report', 'brojevi'), ('report', 'decide', 'pregled')]

evidence, components = [], []
for identity, name, purpose, relative, needle, *_ in specs:
    source = project_root/relative
    lines = source.read_text(encoding='utf-8').splitlines()
    line = next(n for n, text in enumerate(lines, 1) if needle in text)
    evidence.append({'id': identity, 'relativePath': relative, 'line': line,
                     'fileHash': hashlib.sha256(source.read_bytes()).hexdigest()})
    components.append({'id': identity, 'name': name, 'purpose': purpose, 'evidenceIds': [identity]})
analysis = {'schemaVersion': 1, 'projectId': project['id'], 'projectRoot': str(project_root),
            'generatedAt': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'components': components,
            'edges': [{'from': a, 'to': b, 'label': label, 'status': 'observed', 'evidenceIds': [a, b]}
                      for a, b, label in pairs],
            'evidence': evidence, 'openQuestions': []}
native = {'schema_version': 2, 'diagram_type': 'workflow', 'meta': {
    'title': 'session-miner: tok od sesije do odluke', 'quality_profile': 'standard',
    'output': 'output/maps/session-miner.html'},
    'lanes': [{'id': 'input', 'label': 'Ulaz i pohrana'}, {'id': 'analysis', 'label': 'Analiza'},
              {'id': 'output', 'label': 'Izlaz za čovjeka'}],
    'nodes': [{'id': identity, 'lane': lane, 'col': col, 'type': kind, 'label': name}
              for identity, name, _, _, _, lane, col, kind in specs],
    'edges': [{'from': a, 'to': b} for a, b, _ in pairs],
    'cards': [{'dot': 'cyan', 'title': 'Granice', 'items': [
        'Draft-only: ne mijenja instrukcije, skillove ni git.',
        'Bez mrežnih poziva; podaci ostaju lokalno.',
        'Linije i SHA-256 hashovi izvora su u analysis JSON-u.']}]}
folder = root/'data/session-miner-input'
folder.mkdir(parents=True, exist_ok=True)
(folder/'analysis.json').write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding='utf-8')
(folder/'native.json').write_text(json.dumps(native, ensure_ascii=False, indent=2), encoding='utf-8')

code = main(['map', project['id'], '--analysis', 'data/session-miner-input/analysis.json',
             '--input', 'data/session-miner-input/native.json', '--slug', 'session-miner', '--type', 'workflow'])
if code:
    raise SystemExit(code)
env = dict(os.environ, ARCHIFY_UPDATE_CHECK_DISABLED='1')
chromes = sorted((root/'.playwright-browsers').glob('chromium-*/chrome-win64/chrome.exe'))
if chromes and 'ARCHIFY_CHROME' not in env:
    env['ARCHIFY_CHROME'] = str(chromes[-1])
bundled_node = root/'.venv/Lib/site-packages/playwright/driver/node.exe'
node = str(bundled_node) if bundled_node.exists() else shutil.which('node')
if not node:
    raise SystemExit('Za mapu instaliraj Node.js 18+ ili setup -Development.')
result = subprocess.run([node, str(root/'vendor/archify/archify/bin/archify.mjs'), 'finalize', 'workflow',
                         'data/maps/session-miner.json', 'output/maps/session-miner.html',
                         '--quality', 'standard', '--json'], cwd=root, env=env, timeout=180)
sys.exit(result.returncode)
