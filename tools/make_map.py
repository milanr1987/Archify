"""Napravi ili obnovi mapu projekta iz opisa config/maps/<slug>.json.

Upotreba, iz Archify foldera, poslije `atlas refresh`:
    $env:PYTHONPATH = "src"; .\\.venv\\Scripts\\python.exe tools\\make_map.py session-miner
    ... tools\\make_map.py --all
    ... tools\\make_map.py --stale     (samo mape koje nisu „Aktuelna“)

Opisi mapa su privatni (config/maps/ nije u Gitu). Izvori projekta se samo čitaju;
ulazi idu u data/map-input/<slug>/, mapa u output/maps/<slug>.html.
"""
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from atlas.cli import main
from atlas.maps import catalog_maps
from atlas.paths import AppPaths
from atlas.mapspec import build_inputs, validate_spec

root = Path(__file__).resolve().parents[1]


def make(slug: str) -> int:
    spec_path = root/'config/maps'/f'{slug}.json'
    if not spec_path.is_file():
        print(f'Nema opisa mape: {spec_path}', file=sys.stderr)
        return 1
    spec = validate_spec(json.loads(spec_path.read_text(encoding='utf-8')))
    inv = json.loads((root/'data/inventory.json').read_text(encoding='utf-8'))
    projects = [i for i in inv['items'] if i['kind'] == 'project' and i['name'] == spec['project']]
    if len(projects) != 1:
        found = ', '.join(p['locations'][0]['path'] for p in projects) or 'nijedan'
        print(f"Projekat {spec['project']!r} mora biti tačno jedan u katalogu (nađeno: {found}).", file=sys.stderr)
        return 1
    project = projects[0]
    analysis, native = build_inputs(spec, project['id'], Path(project['locations'][0]['path']),
                                    datetime.now(timezone.utc))
    folder = root/'data/map-input'/slug
    folder.mkdir(parents=True, exist_ok=True)
    (folder/'analysis.json').write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding='utf-8')
    (folder/'native.json').write_text(json.dumps(native, ensure_ascii=False, indent=2), encoding='utf-8')
    code = main(['map', project['id'], '--analysis', f'data/map-input/{slug}/analysis.json',
                 '--input', f'data/map-input/{slug}/native.json', '--slug', slug, '--type', 'workflow'])
    if code:
        return code
    env = dict(os.environ, ARCHIFY_UPDATE_CHECK_DISABLED='1')
    chromes = sorted((root/'.playwright-browsers').glob('chromium-*/chrome-win64/chrome.exe'))
    if chromes and 'ARCHIFY_CHROME' not in env:
        env['ARCHIFY_CHROME'] = str(chromes[-1])
    bundled_node = root/'.venv/Lib/site-packages/playwright/driver/node.exe'
    node = str(bundled_node) if bundled_node.exists() else shutil.which('node')
    if not node:
        print('Za provjeru mape instaliraj Node.js 18+ ili pokreni setup -Development.', file=sys.stderr)
        return 1
    result = subprocess.run([node, str(root/'vendor/archify/archify/bin/archify.mjs'), 'finalize', 'workflow',
                             f'data/maps/{slug}.json', f'output/maps/{slug}.html', '--quality', 'standard'],
                            cwd=root, env=env, timeout=180)
    return result.returncode


if __name__ == '__main__':
    args = sys.argv[1:]
    if args == ['--all']:
        args = sorted(p.stem for p in (root/'config/maps').glob('*.json'))
    elif args == ['--stale']:
        specs = {p.stem for p in (root/'config/maps').glob('*.json')}
        args = sorted(Path(m['htmlPath']).stem for m in catalog_maps(AppPaths(root))
                      if m['status'] != 'current' and Path(m['htmlPath']).stem in specs)
        if not args:
            print('Sve mape su aktuelne; nema šta obnavljati.')
            raise SystemExit(0)
    if not args:
        raise SystemExit(__doc__)
    raise SystemExit(max(make(slug) for slug in args))
