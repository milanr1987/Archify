"""Hash source configs and discovered project .mcp.json files; never print contents."""
import hashlib, json, sys
from pathlib import Path
from atlas.config import load_config
from atlas.scan.projects import scan_projects
from atlas.scan.collector import Collector

def main():
    config=load_config(Path(sys.argv[1]))
    projects=scan_projects(config, Collector())
    files=sorted({r.path for r in config.plugin_registries} | {m.path for m in config.mcp_sources}
                 | {p for _, p in projects.mcp_files})
    result={}
    for path in files:
        try: result[path]=hashlib.sha256(Path(path).read_bytes()).hexdigest()
        except FileNotFoundError: result[path]=None
        except OSError: result[path]='unreadable'
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return 0
if __name__=='__main__':raise SystemExit(main())
