"""Privatnost Faze 6 i nepromijenjeni izvori, samo privremeni fixture repoi."""
import contextlib
import hashlib
import io
import json
import os
import subprocess
from unittest.mock import patch

from helpers import TempDirTestCase, make_fixture, write, SENTINELS
from atlas.cli import main
from atlas.scan.state import encode_project


class StateIntegrationTests(TempDirTestCase):
    def test_refresh_keeps_sources_and_git_index_and_excludes_session_secrets(self):
        cfg=make_fixture(self.tmp)
        project=self.tmp/'workspace čćž'/'proj-node'
        index=write(project/'.git'/'index','FAKE INDEX')
        session_secret='SENTINEL-SESSION-CONTENT-PHASE6'
        session=write(self.tmp/'home'/'.claude'/'projects'/encode_project(project)/'one.jsonl',session_secret)
        os.utime(session,(1000,1000))
        app=self.tmp/'app'
        write(app/'config'/'sources.local.json',json.dumps(cfg))
        paths=[p for folder in (self.tmp/'home',self.tmp/'workspace čćž') for p in folder.rglob('*') if p.is_file()]
        def snapshot():
            return {str(p):(p.stat().st_mtime_ns,hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths}
        before=snapshot()
        def fake_git(args, **kwargs):
            self.assertFalse(kwargs['shell'])
            self.assertEqual(kwargs['env']['GIT_OPTIONAL_LOCKS'],'0')
            output='2026-10-14T10:00:00+00:00\n' if 'log' in args else ' M tracked\n' if 'status' in args else 'main\n'
            return subprocess.CompletedProcess(args,0,output,'')
        with patch('atlas.scan.state.subprocess.run',side_effect=fake_git), contextlib.redirect_stdout(io.StringIO()):
            code=main(['refresh'],app_root=app)
        self.assertIn(code,(0,2))
        self.assertEqual(before,snapshot())
        self.assertIn(str(index),before)
        for folder in (app/'data',app/'output'):
            outputs=[p for p in folder.rglob('*') if p.is_file()]
            self.assertTrue(outputs)
            for p in outputs:
                text=p.read_text(encoding='utf-8')
                for secret in (*SENTINELS,session_secret,'FAKE INDEX'):
                    self.assertNotIn(secret,text)
        inv=json.loads((app/'data'/'inventory.json').read_text(encoding='utf-8'))
        item=next(i for i in inv['items'] if i['kind']=='project' and i['name']=='proj-node')
        self.assertEqual(item['metadata']['dirtyCount'],'1')
        self.assertEqual(item['metadata']['lastSessionAt'],'1970-01-01T00:16:40+00:00')

    def test_legacy_inventory_builds_without_refresh(self):
        from atlas.model import Inventory,Item,Location,SCHEMA_VERSION,inventory_to_dict
        from atlas.identity import make_id
        app=self.tmp/'app'
        inv=Inventory(SCHEMA_VERSION,'2026-10-14T00:00:00+00:00',[Item(make_id('skill','old'),'skill','old',locations=[Location('old','max')])],[],[],False)
        data=inventory_to_dict(inv)
        data.pop('profiles',None)
        for loc in data['items'][0]['locations']:loc.pop('contentHash',None)
        write(app/'data'/'inventory.json',json.dumps(data))
        with contextlib.redirect_stdout(io.StringIO()):code=main(['build'],app_root=app)
        self.assertEqual(code,0)
        self.assertTrue((app/'output'/'index.html').is_file())
