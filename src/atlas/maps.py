"""Local source evidence and an offline Archify adapter."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

MAX_FILE = 8 * 1024 * 1024
MAX_JSON = 1024 * 1024
SLUG = r'[a-z0-9]+(?:-[a-z0-9]+)*'
HEX = r'[a-f0-9]{64}'


class MapError(ValueError):
    pass


def _require(condition, code='map-invalid'):
    if not condition:
        raise MapError(code)


def _strings(value):
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def bounded_json(value) -> str:
    text = json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')) + '\n'
    _require(len(text.encode('utf-8')) <= MAX_JSON, 'map-json-too-large')
    return text


def _read_json(path: Path):
    with path.open('rb') as stream:
        raw = stream.read(MAX_JSON + 1)
    _require(len(raw) <= MAX_JSON, 'map-json-too-large')
    try:
        return json.loads(raw.decode('utf-8-sig'))
    except (ValueError, UnicodeError, RecursionError):
        raise MapError('map-invalid-json') from None


def _source(root: Path, relative: str) -> Path:
    _require(isinstance(relative, str) and relative != '')
    p = Path(relative)
    _require(not p.is_absolute() and not p.drive and '..' not in p.parts)
    _require(not any(part.startswith('.') or any(word in part.lower()
        for word in ('credentials', 'auth', 'token', 'secret')) for part in p.parts), 'map-private-source')
    target = (root / p).resolve()
    _require(target.is_relative_to(root.resolve()), 'map-source-outside-root')
    _require(not any(part.startswith('.') or any(word in part.lower()
        for word in ('credentials','auth','token','secret'))
        for part in target.relative_to(root.resolve()).parts), 'map-private-source')
    return target


def validate_analysis(data: object) -> dict:
    _require(isinstance(data, dict) and set(data) == {'schemaVersion','projectId','projectRoot',
        'generatedAt','components','edges','evidence','openQuestions'})
    _require(type(data['schemaVersion']) is int and data['schemaVersion'] == 1)
    _require(isinstance(data['projectId'], str) and re.fullmatch(HEX, data['projectId']))
    _require(isinstance(data['projectRoot'], str) and Path(data['projectRoot']).is_absolute())
    _require(isinstance(data['generatedAt'], str) and data['generatedAt'])
    _require(_strings(data['openQuestions']))
    for field in ('components','edges','evidence'):
        _require(isinstance(data[field], list))
    evidence_ids = set()
    root = Path(data['projectRoot'])
    for e in data['evidence']:
        _require(isinstance(e, dict) and set(e) == {'id','relativePath','line','fileHash'})
        _require(isinstance(e['id'], str) and e['id'] and e['id'] not in evidence_ids)
        evidence_ids.add(e['id'])
        _source(root, e['relativePath'])
        _require(type(e['line']) is int and e['line'] > 0)
        _require(isinstance(e['fileHash'], str) and re.fullmatch(HEX, e['fileHash']))
    components = set()
    for c in data['components']:
        _require(isinstance(c, dict) and set(c) == {'id','name','purpose','evidenceIds'})
        _require(all(isinstance(c[k], str) and c[k] for k in ('id','name','purpose')))
        _require(c['id'] not in components)
        components.add(c['id'])
        _require(_strings(c['evidenceIds']) and set(c['evidenceIds']) <= evidence_ids)
    for e in data['edges']:
        _require(isinstance(e, dict) and set(e) == {'from','to','label','status','evidenceIds'})
        _require(isinstance(e['from'], str) and isinstance(e['to'], str) and
                 e['from'] in components and e['to'] in components)
        _require(isinstance(e['label'], str) and e['status'] in ('observed','documented'))
        _require(_strings(e['evidenceIds']) and set(e['evidenceIds']) <= evidence_ids)
    return data


def source_fingerprint(analysis: dict) -> str:
    validate_analysis(analysis)
    pairs = sorted({(e['relativePath'], e['fileHash']) for e in analysis['evidence']})
    return hashlib.sha256(json.dumps(pairs, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def map_status(analysis: dict) -> str:
    validate_analysis(analysis)
    incomplete = (not analysis['evidence'] or not analysis['components'] or
                  bool(analysis['openQuestions']) or
                  any(not v['evidenceIds'] for v in analysis['components'] + analysis['edges']))
    changed = False
    for e in analysis['evidence']:
        source = _source(Path(analysis['projectRoot']), e['relativePath'])
        try:
            with source.open('rb') as stream:
                raw = stream.read(MAX_FILE + 1)
            if len(raw) > MAX_FILE:
                incomplete = True
            elif hashlib.sha256(raw).hexdigest() != e['fileHash']:
                changed = True
            elif e['line'] > len(raw.splitlines()):
                incomplete = True
        except FileNotFoundError:
            changed = True
        except OSError:
            incomplete = True
    return 'stale' if changed else ('unverified' if incomplete else 'current')


def validate_registry(data: object) -> list[dict]:
    _require(isinstance(data, dict) and set(data) == {'schemaVersion','maps'})
    _require(type(data['schemaVersion']) is int and data['schemaVersion'] == 1 and isinstance(data['maps'], list))
    seen = set()
    for entry in data['maps']:
        _require(isinstance(entry, dict) and set(entry) == {'projectId','title','htmlPath',
            'analysisPath','generatedAt','sourceFingerprint'})
        _require(all(isinstance(v, str) for v in entry.values()))
        _require(re.fullmatch(HEX, entry['projectId']) and re.fullmatch(HEX, entry['sourceFingerprint']))
        _require(re.fullmatch('maps/'+SLUG+r'\.html', entry['htmlPath']))
        _require(re.fullmatch('analysis/'+SLUG+r'\.json', entry['analysisPath']))
        _require(entry['title'] and entry['generatedAt'])
        _require(entry['htmlPath'] not in seen)
        seen.add(entry['htmlPath'])
    return data['maps']


def load_registry(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return validate_registry(_read_json(path))


def map_output_allowed(paths, target: Path) -> bool:
    resolved = target.resolve()
    if resolved == paths.map_registry.resolve():
        return True
    return any(resolved.parent == folder.resolve() and re.fullmatch(SLUG + suffix, target.name)
               for folder, suffix in ((paths.data_dir/'analysis', r'\.json'),
                                      (paths.data_dir/'maps', r'\.json'),
                                      (paths.output_dir/'maps', r'\.html')))


def validate_catalog_maps(value: object) -> list[dict]:
    _require(isinstance(value, list))
    for entry in value:
        _require(isinstance(entry, dict) and entry.get('status') in ('current','stale','unverified'))
    validate_registry({'schemaVersion':1,'maps':[
        {k:v for k,v in entry.items() if k != 'status'} for entry in value]})
    return value


def catalog_maps(paths) -> list[dict]:
    result = []
    for entry in load_registry(paths.map_registry):
        status = 'unverified'
        try:
            analysis = validate_analysis(_read_json(paths.data_dir / entry['analysisPath']))
            if analysis['projectId'] == entry['projectId'] and source_fingerprint(analysis) == entry['sourceFingerprint']:
                status = map_status(analysis)
            if not (paths.output_dir / entry['htmlPath']).is_file():
                status = 'unverified'
        except (OSError, MapError):
            pass
        result.append({**entry, 'status':status})
    return result


def render_map(root: Path, kind: str, source: Path, output: Path) -> str:
    _require(kind in ('workflow','architecture'))
    node = root / '.venv/Lib/site-packages/playwright/driver/node.exe'
    executable = str(node) if node.exists() else (shutil.which('node') or 'node')
    cli = root / 'vendor/archify/archify/bin/archify.mjs'
    env = dict(os.environ, ARCHIFY_UPDATE_CHECK_DISABLED='1')
    for command in ([executable,str(cli),'validate',kind,str(source),'--quality','standard','--json'],
                    [executable,str(cli),'render',kind,str(source),str(output)]):
        try:
            completed = subprocess.run(command,cwd=root,env=env,capture_output=True,
                                       timeout=120, encoding='utf-8', errors='replace')
        except (OSError, subprocess.TimeoutExpired):
            raise MapError('archify-unavailable-or-timeout') from None
        if completed.returncode != 0:
            # Never print authored data or arbitrary diagnostics that might contain secrets.
            raise MapError('archify-command-failed')
    try:
        html = output.read_text(encoding='utf-8')
    except OSError:
        raise MapError('archify-no-output') from None
    _require('<html' in html.lower() and '<svg' in html.lower(), 'archify-invalid-html')
    return html
