"""Ograničeni read-only hash, Git i mtime; nikada ne izvozi sadržaj."""
import hashlib
import os
import re
import shutil
import stat
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from atlas.fsutil import is_within
from atlas.scan.collector import Collector
from atlas.state import skill_groups


def content_hash(root, collector, *, max_files=1024, max_bytes=64*1024*1024, max_file_bytes=16*1024*1024):
    root = Path(root).resolve()
    files = []
    folders = []
    entries = 0
    total = 0
    try:
        def walk(folder, depth, stack):
            nonlocal entries, total
            real = folder.resolve()
            if not is_within(str(real),str(root)) or real in stack or depth>32:
                raise ValueError('unsafe-link')
            stack=stack|{real}
            folders.append((folder,folder.stat().st_mtime_ns))
            with os.scandir(folder) as listing:
                for entry in listing:
                    entries+=1
                    if entries>4096: raise ValueError('limit')
                    path=Path(entry.path)
                    if not is_within(str(path),str(root)): raise ValueError('outside-link')
                    if entry.is_dir(): walk(path,depth+1,stack)
                    else:
                        # Windows DirEntry.stat can report st_ino=0; use stat on the path.
                        info=path.stat()
                        if not stat.S_ISREG(info.st_mode): raise ValueError('special-file')
                        total+=info.st_size
                        files.append((path.relative_to(root).as_posix(),path,info))
                        if len(files)>max_files or total>max_bytes or info.st_size>max_file_bytes:
                            raise ValueError('limit')
        walk(root,0,frozenset())
        digest=hashlib.sha256(b'atlas-skill-v1\0')
        for rel,path,info in sorted(files):
            if not is_within(str(path),str(root)): raise ValueError('changed-link')
            with path.open('rb') as handle:
                before=os.fstat(handle.fileno())
                if not stat.S_ISREG(before.st_mode): raise ValueError('special-file')
                data=handle.read(min(max_file_bytes,max_bytes)+1)
                after=os.fstat(handle.fileno())
            if len(data)!=info.st_size or len(data)>max_file_bytes or (before.st_mtime_ns,before.st_size,before.st_ino)!=(after.st_mtime_ns,after.st_size,after.st_ino) or (before.st_mtime_ns,before.st_ino)!=(info.st_mtime_ns,info.st_ino):
                raise ValueError('changed-file')
            encoded=rel.encode('utf-8')
            digest.update(len(encoded).to_bytes(8,'big'));digest.update(encoded)
            digest.update(len(data).to_bytes(8,'big'));digest.update(data)
        if any(folder.stat().st_mtime_ns!=mtime for folder,mtime in folders):raise ValueError('changed-folder')
        return digest.hexdigest()
    except (OSError,ValueError,RuntimeError):
        collector.warn('warn','skill-hash-unknown',root,'hash nije dostupan: limit, nečitljiv/promijenjen fajl ili nesiguran link')
        return 'unknown'


def git_executable():
    found=shutil.which('git')
    if found: return found
    portable=Path(__file__).resolve().parents[3]/'.tools/git/ucrt64/bin/git.exe'
    return str(portable) if portable.is_file() else None


def project_git(root, collector, *, git=None):
    unknown={k:'unknown' for k in ('lastCommitAt','dirtyCount','branch')}
    git=git or git_executable()
    try:
        if not git or not (Path(root)/'.git').exists(): raise ValueError('no-git')
        env={k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
        env.update(GIT_TERMINAL_PROMPT='0',GIT_OPTIONAL_LOCKS='0')
        results=[]
        for args in [('log','-1','--format=%cI'),('status','--porcelain'),('rev-parse','--abbrev-ref','HEAD')]:
            result=subprocess.run([git,'--no-optional-locks','-c','core.fsmonitor=false','-C',str(root),*args],
                shell=False,timeout=5,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if result.returncode or len(result.stdout)>8*1024*1024:raise ValueError('git-error')
            results.append(result.stdout)
        date=datetime.fromisoformat(results[0].strip())
        if not date.tzinfo or not results[2].strip():raise ValueError('invalid-git')
        return {'lastCommitAt':date.astimezone(timezone.utc).isoformat(),'dirtyCount':str(len(results[1].splitlines())), 'branch':results[2].strip()}
    except (OSError,ValueError,subprocess.SubprocessError):
        collector.warn('info','project-git-unknown',root,'Git stanje nije dostupno (bez repozitorija, greška ili timeout)')
        return unknown


def encode_project(path):
    return re.sub(r'[^A-Za-z0-9]','-',str(path))


def session_roots(config):
    roots=set()
    for r in config.skill_roots:
        p=Path(r.path)
        if p.name.lower()=='skills' and p.parent.name.lower().startswith('.claude'):
            roots.add((r.profile,str(p.parent)))
    for src in config.mcp_sources:
        p=Path(src.path)
        if src.format=='claude-json' and p.name=='settings.json':roots.add((src.profile,str(p.parent)))
    for reg in config.plugin_registries:
        p=Path(reg.path).parent
        if p.name.lower()=='plugins' and p.parent.name.lower().startswith('.claude'):
            roots.add((reg.profile,str(p.parent)))
    return sorted(roots)


def session_time(profile_root, project, collector):
    root=Path(profile_root)/'projects'/encode_project(project)
    if not root.is_dir():return 'unknown'
    latest=None
    try:
        count=0
        def on_error(error):
            raise error
        for folder,dirs,files in os.walk(root,followlinks=False,onerror=on_error):
            count+=len(dirs)
            if count>10000:raise ValueError('session-limit')
            dirs[:]=sorted(d for d in dirs if is_within(str(Path(folder)/d),str(root)) and not Path(folder,d).is_symlink() and not (hasattr(Path(folder,d),'is_junction') and Path(folder,d).is_junction()))
            for name in sorted(files):
                count+=1
                if count>10000:raise ValueError('session-limit')
                path=Path(folder,name)
                if path.suffix.lower()=='.jsonl' and is_within(str(path),str(root)) and not path.is_symlink():
                    value=path.stat().st_mtime
                    latest=max(latest,value) if latest is not None else value
        return datetime.fromtimestamp(latest,timezone.utc).isoformat() if latest is not None else 'unknown'
    except (OSError,ValueError,OverflowError):
        collector.warn('info','project-session-unknown',project,'mtime sesije nije dostupan')
        return 'unknown'


def enrich_state(config, collector):
    start=time.perf_counter()
    projects=sorted((i for i in collector.items.values() if i.kind=='project'),key=lambda i:i.id)
    def inspect(item):
        c=Collector()
        return project_git(item.locations[0].path,c),c.warnings
    with ThreadPoolExecutor(max_workers=8) as pool:
        for item,(metadata,warnings) in zip(projects,pool.map(inspect,projects)):
            item.metadata.update(metadata);collector.warnings.extend(warnings)
    git_seconds=time.perf_counter()-start
    encoded={}
    for item in projects:
        encoded.setdefault(encode_project(item.locations[0].path),set()).add(os.path.normcase(os.path.realpath(item.locations[0].path)))
    for item in projects:
        path=item.locations[0].path
        dates=[]
        if len(encoded[encode_project(path)])>1:
            collector.warn('info','session-path-collision',path,'kodirana putanja nije jednoznačna; sesije nisu pridružene')
        else:
            for profile,root in session_roots(config):
                value=session_time(root,path,collector)
                if value!='unknown':dates.append((profile,value))
        item.metadata['lastSessionAt']=max((v for _,v in dates),default='unknown')
        item.metadata['sessionTimes']=[f'{p}: {v}' for p,v in sorted(dates)]
    for group in skill_groups(list(collector.items.values())):
        for iid in group['itemIds']:
            collector.items[iid].metadata.update(contentStatus=group['status'],ownDrift='true' if group['ownDrift'] else 'false')
    return git_seconds
