"""Transactional publication of rendered project maps."""
import json
import re
import tempfile
from pathlib import Path

from atlas.maps import (MapError, SLUG, validate_analysis, source_fingerprint, map_status,
    load_registry, catalog_maps, render_map, _read_json, validate_registry, bounded_json)
from atlas.model import inventory_from_dict, inventory_hash
from atlas.overlay import load_overlay
from atlas.outputs import catalog_target
from atlas.writeout import Target, publish


def publish_map(paths, project_id: str, analysis_path: str, input_path: str, slug: str, kind: str) -> int:
    if not re.fullmatch(SLUG, slug):
        raise MapError('map-invalid-slug')
    inv = inventory_from_dict(json.loads(paths.inventory.read_text(encoding='utf-8')))
    project = next((it for it in inv.items if it.id == project_id and it.kind == 'project'), None)
    if project is None:
        raise MapError('map-unknown-project')
    def local_arg(value):
        p = Path(value)
        return p if p.is_absolute() else paths.root / p
    analysis = validate_analysis(_read_json(local_arg(analysis_path)))
    if analysis['projectId'] != project_id or not any(
            Path(loc.path).resolve() == Path(analysis['projectRoot']).resolve() for loc in project.locations):
        raise MapError('map-project-identity-mismatch')
    native = _read_json(local_arg(input_path))
    if not isinstance(native, dict) or not isinstance(native.get('meta'), dict):
        raise MapError('map-invalid-native-input')
    registry = load_registry(paths.map_registry)
    overlay = load_overlay(paths.overrides)
    entry = {'projectId':project_id, 'title':native['meta'].get('title',project.name),
        'htmlPath':f'maps/{slug}.html','analysisPath':f'analysis/{slug}.json',
        'generatedAt':analysis['generatedAt'],'sourceFingerprint':source_fingerprint(analysis)}
    registry = [v for v in registry if v['htmlPath'] != entry['htmlPath']] + [entry]
    validate_registry({'schemaVersion':1,'maps':registry})
    analysis_text = bounded_json(analysis)
    registry_text = bounded_json({'schemaVersion':1,'maps':registry})
    paths.data_dir.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='map-stage-',dir=paths.data_dir) as tmp:
        stage = Path(tmp)
        native['meta']['output'] = (stage/'map.html').relative_to(paths.root).as_posix()
        candidate = stage/'candidate.json'
        candidate.write_text(bounded_json(native),encoding='utf-8')
        html = render_map(paths.root,kind,candidate,stage/'map.html')
    native['meta']['output'] = 'output/'+entry['htmlPath']
    def check_analysis(text): validate_analysis(json.loads(text))
    def check_registry(text): validate_registry(json.loads(text))
    def check_html(text):
        if '<html' not in text.lower() or '<svg' not in text.lower():
            raise MapError('map-invalid-html')
    current_maps = [v for v in catalog_maps(paths) if v['htmlPath'] != entry['htmlPath']]
    current_maps.append({**entry,'status':map_status(analysis)})
    targets = [
        Target(paths.data_dir/entry['analysisPath'],analysis_text,check_analysis),
        Target(paths.data_dir/'maps'/f'{slug}.json',bounded_json(native),json.loads),
        Target(paths.output_dir/entry['htmlPath'],html,check_html),
        Target(paths.map_registry,registry_text,check_registry),
        catalog_target(paths,inv,inventory_hash(inv),overlay,current_maps)]
    publish(paths, targets)
    print(f'Mapa: {paths.output_dir/entry["htmlPath"]}')
    return 0
