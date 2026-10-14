"""Prepare a local Atlas demonstration from inspected source evidence."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from atlas.cli import main
from atlas.config import default_config

root = Path(__file__).resolve().parents[1]
config_path = root / 'config/sources.current.json'
if not config_path.exists():
    config = default_config(Path.home(), root.parent)
    config['extraProjects'] = [str(root)]
    config['documents'] = [{'path':str(root/'README.md'),'title':'Atlas README'}]
    for field in ('skillRoots','pluginRegistries','mcpSources'):
        config[field] = [item for item in config[field] if Path(item['path']).exists()]
    codex_skills = Path.home()/'.codex/skills'
    if codex_skills.exists():
        config['skillRoots'].append({'path':str(codex_skills),'profile':'codex','label':'.codex skills'})
    config_path.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
else:
    config = json.loads(config_path.read_text(encoding='utf-8'))
    if str(root) not in config['extraProjects']:
        config['extraProjects'].append(str(root))
        config_path.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
code = main(['refresh','--config',str(config_path)])
if code not in (0,2):
    raise SystemExit(code)
inv = json.loads((root/'data/inventory.json').read_text(encoding='utf-8'))
project = next(item for item in inv['items'] if item['kind']=='project' and
               any(Path(loc['path']).resolve()==root for loc in item['locations']))
specs = [
    ('cli','CLI refresh','src/atlas/cli.py','def _cmd_refresh','Priprema refresh komandu'),
    ('config','Konfiguracija','src/atlas/config.py','def load_config','Ucita deklarisane izvore'),
    ('scan','Skeniranje','src/atlas/inventory.py','def build_inventory','Poziva read-only skenere'),
    ('inventory','Inventar','src/atlas/inventory.py','def finalize','Spaja i validira stavke'),
    ('catalog','HTML renderer','src/atlas/catalog.py','def render_catalog','Ugradjuje podatke i UI'),
    ('publish','Objava','src/atlas/writeout.py','def publish','Staging, backup i journal'),
    ('recover','Oporavak','src/atlas/writeout.py','def recover_if_needed','Oporavlja prekinutu objavu'),
    ('browser','Offline prikaz','src/atlas/ui/app.js','function renderDetail','Prikazuje odabranu stavku')]
evidence, components = [], []
for identity,name,relative,needle,purpose in specs:
    source = root/relative
    lines = source.read_text(encoding='utf-8').splitlines()
    line = next(n for n,text in enumerate(lines,1) if needle in text)
    evidence.append({'id':identity,'relativePath':relative,'line':line,
                     'fileHash':hashlib.sha256(source.read_bytes()).hexdigest()})
    components.append({'id':identity,'name':name,'purpose':purpose,'evidenceIds':[identity]})
pairs = [('cli','config'),('cli','scan'),('scan','inventory'),('cli','catalog'),
         ('cli','publish'),('recover','publish'),('catalog','browser')]
analysis = {'schemaVersion':1,'projectId':project['id'],'projectRoot':str(root),
    'generatedAt':datetime.now(timezone.utc).isoformat(),'components':components,
    'edges':[{'from':a,'to':b,'label':'lokalni tok','status':'documented',
              'evidenceIds':[a,b]} for a,b in pairs], 'evidence':evidence,
    'openQuestions':['Demonstraciona mapa; nije mapa creative-forge ili session-miner.']}
native = {'schema_version':2,'diagram_type':'workflow','meta':{
    'title':'Atlas: lokalna demonstraciona mapa','quality_profile':'standard',
    'output':'output/maps/atlas-demo.html'},
    'lanes':[{'id':'prepare','label':'Priprema podataka'},{'id':'deliver','label':'Lokalna isporuka'}],
    'nodes':[], 'edges':[]}
for n,(identity,name,relative,needle,purpose) in enumerate(specs):
    native['nodes'].append({'id':identity,'lane':'prepare' if n<4 else 'deliver',
        'col':n if n<4 else n-2,'type':'frontend' if identity=='browser' else 'backend',
        'label':name})
native['edges'] = [{'from':a,'to':b} for a,b in pairs]
native['cards'] = [{'dot':'cyan','title':'Granice dokaza','items':[
    'Lokalni hashovi i linije su u analysis JSON-u.',
    'Ovo je demo Atlasa, bez tvrdnje o upstream Git verifikaciji.',
    'creative-forge i session-miner nisu dostupni na ovom racunaru.']}]
folder = root/'data/demo-input'
folder.mkdir(parents=True,exist_ok=True)
(folder/'analysis.json').write_text(json.dumps(analysis,ensure_ascii=False,indent=2),encoding='utf-8')
(folder/'native.json').write_text(json.dumps(native,ensure_ascii=False,indent=2),encoding='utf-8')
print('Demo project ID:', project['id'])
