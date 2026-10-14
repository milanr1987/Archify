import json
import os
import subprocess
from datetime import datetime, timezone
from unittest.mock import patch

from helpers import TempDirTestCase, write, skill_md, make_dir_link
from atlas.config import parse_config
from atlas.model import Item, Location, Inventory, SCHEMA_VERSION, canonical_json, inventory_from_dict, validate_inventory, InventoryError
from atlas.identity import make_id
from atlas.scan.collector import Collector


class StateTests(TempDirTestCase):
    def test_hash_content_paths_and_order(self):
        from atlas.scan.state import content_hash
        a, b = self.tmp/'a', self.tmp/'b'
        for root, order in [(a, ['z', 'a']), (b, ['a', 'z'])]:
            for name in order: write(root/name, name)
        c = Collector()
        self.assertEqual(content_hash(a, c), content_hash(b, c))
        write(b/'z', 'different')
        self.assertNotEqual(content_hash(a, c), content_hash(b, c))
        (b/'z').rename(b/'y')
        self.assertNotEqual(content_hash(a, c), content_hash(b, c))

    def test_hash_limit_and_external_link_are_unknown(self):
        from atlas.scan.state import content_hash
        root = self.tmp/'skill';write(root/'SKILL.md', 'body')
        c = Collector()
        self.assertEqual(content_hash(root, c, max_bytes=2), 'unknown')
        self.assertEqual(c.warnings[0].severity, 'warn')
        outside = self.tmp/'outside';write(outside/'secret', 'DO-NOT-EXPORT')
        make_dir_link(root/'escape', outside)
        self.assertEqual(content_hash(root, c), 'unknown')
        self.assertNotIn('DO-NOT-EXPORT', str(c.warnings))

    def test_hash_binary_file_and_file_count(self):
        from atlas.scan.state import content_hash
        root=self.tmp/'skill';write(root/'x','x');(root/'b').write_bytes(b'\x00\xff')
        self.assertEqual(len(content_hash(root, Collector())),64)
        self.assertEqual(content_hash(root, Collector(), max_files=1), 'unknown')

    def test_hash_internal_link_cycle_and_unreadable_are_unknown(self):
        from atlas.scan.state import content_hash
        root=self.tmp/'skill';write(root/'a','a')
        make_dir_link(root/'cycle',root)
        self.assertEqual(content_hash(root,Collector()),'unknown')
        with patch('atlas.scan.state.os.scandir',side_effect=PermissionError):
            self.assertEqual(content_hash(root,Collector()),'unknown')

    def test_hash_changed_file_is_unknown(self):
        from atlas.scan.state import content_hash
        root=self.tmp/'skill';write(root/'a','a')
        original=os.fstat
        def changed(fd):
            info=original(fd)
            return type('Stat',(),{'st_mode':info.st_mode,'st_mtime_ns':info.st_mtime_ns+1,'st_size':info.st_size,'st_ino':info.st_ino})()
        with patch('atlas.scan.state.os.fstat',side_effect=changed):
            self.assertEqual(content_hash(root,Collector()),'unknown')

    def test_session_roots_include_registry_only_claude_profile(self):
        from atlas.scan.state import session_roots
        root=self.tmp/'.claude-max'
        cfg=parse_config({'workspaceRoot':str(self.tmp),'pluginRegistries':[{'path':str(root/'plugins'/'installed_plugins.json'),'profile':'max'}]})
        self.assertEqual(session_roots(cfg),[('max',str(root))])

    def skill(self, name, path, profile, hash_, origin='standalone'):
        return Item(make_id('skill',path), 'skill',name,locations=[Location(path,profile,origin=origin,contentHash=hash_)])

    def test_comparison_separates_plugin_versions_and_own_skills(self):
        from atlas.state import skill_groups
        p1=Item(make_id('plugin','1'),'plugin','tool',locations=[Location('p1')],metadata={'version':'1','marketplace':'m'})
        p2=Item(make_id('plugin','2'),'plugin','tool',locations=[Location('p2')],metadata={'version':'2','marketplace':'m'})
        own1=self.skill('same','a','max','a'*64);own2=self.skill('same','b','pro','b'*64)
        plugin1=self.skill('same','c','max','c'*64,'plugin:'+p1.id)
        plugin2=self.skill('same','d','pro','d'*64,'plugin:'+p2.id)
        groups=skill_groups([p1,p2,own1,own2,plugin1,plugin2])
        self.assertEqual(groups[0]['status'],'razlikuje se')
        self.assertTrue(groups[0]['ownDrift'])
        only=skill_groups([p1,p2,plugin1,plugin2])
        self.assertEqual(only[0]['status'],'isti')
        own2.locations[0].contentHash='unknown'
        self.assertEqual(skill_groups([own1,own2])[0]['status'],'nepoznato')

    def test_same_plugin_version_drift_but_different_plugin_is_not_drift(self):
        from atlas.state import skill_groups
        p=Item(make_id('plugin','p'),'plugin','tool',locations=[Location('p')],metadata={'version':'1','marketplace':'m'})
        a=self.skill('same','a','max','a'*64,'plugin:'+p.id)
        b=self.skill('same','b','pro','b'*64,'plugin:'+p.id)
        g=skill_groups([p,a,b])[0]
        self.assertEqual(g['status'],'razlikuje se');self.assertFalse(g['ownDrift'])
        q=Item(make_id('plugin','q'),'plugin','other',locations=[Location('q')],metadata={'version':'1','marketplace':'m'})
        b.locations[0].origin='plugin:'+q.id
        self.assertEqual(skill_groups([p,q,a,b])[0]['status'],'isti')

    def test_shared_location_hashes_same_across_profiles(self):
        from atlas.state import skill_groups
        item=self.skill('same','a','max','a'*64)
        item.locations.append(Location('linked','pro',origin='standalone',contentHash='a'*64))
        group=skill_groups([item])[0]
        self.assertTrue(group['multiple']);self.assertEqual(group['status'],'isti')

    def test_matrix_preserves_empty_profiles_without_hook_payload(self):
        from atlas.state import hook_matrix
        hook=Item(make_id('hook','h'),'hook','PreToolUse',locations=[Location('settings','max',origin='standalone')],metadata={'event':'PreToolUse','matcher':'Bash','hookCount':'2','hookTypes':['command']})
        rows=hook_matrix([hook], ['max','pro'])
        self.assertEqual(rows[0]['cells']['pro'],[])
        self.assertEqual(rows[0]['cells']['max'][0]['origin'],'settings')
        self.assertEqual(rows[0]['cells']['max'][0]['hookCount'],2)
        hook.locations.append(Location('plugin/hooks','max',origin='plugin:'+'a'*64))
        rows=hook_matrix([hook],['max','pro'])
        self.assertEqual({e['origin'] for e in rows[0]['cells']['max']},{'plugin','settings'})

    def test_git_readonly_commands_and_errors(self):
        from atlas.scan.state import project_git
        root=self.tmp/'repo';(root/'.git').mkdir(parents=True)
        c=Collector()
        outputs=['2026-10-14T10:00:00+02:00\n',' M a\n?? dir/\n','main\n']
        with patch('atlas.scan.state.subprocess.run', side_effect=[subprocess.CompletedProcess([],0,x,'') for x in outputs]) as run:
            result=project_git(root,c,git='git')
        self.assertEqual(result['dirtyCount'],'2')
        self.assertEqual(result['branch'],'main')
        for call in run.call_args_list:
            self.assertFalse(call.kwargs['shell'])
            self.assertEqual(call.kwargs['timeout'],5)
            self.assertEqual(call.kwargs['env']['GIT_TERMINAL_PROMPT'],'0')
            self.assertIn('--no-optional-locks', call.args[0])
        with patch('atlas.scan.state.subprocess.run', side_effect=subprocess.TimeoutExpired('git',5)):
            self.assertEqual(project_git(root,c,git='git')['branch'],'unknown')
        self.assertTrue(all(w.severity=='info' for w in c.warnings))

    def test_session_mtime_never_opens_jsonl(self):
        from atlas.scan.state import session_time, encode_project
        project=str(self.tmp/'repo');root=self.tmp/'.claude'
        f=write(root/'projects'/encode_project(project)/'nested'/'one.jsonl','SECRET SESSION')
        os.utime(f,(1000,1000))
        with patch('builtins.open', side_effect=AssertionError('must not open')):
            value=session_time(root,project,Collector())
        self.assertEqual(value,'1970-01-01T00:16:40+00:00')
        self.assertEqual(encode_project(r'C:\Users\X\proj'),'C--Users-X-proj')

    def test_session_missing_external_link_and_newest_mtime(self):
        from atlas.scan.state import session_time,encode_project
        root=self.tmp/'.claude';project=str(self.tmp/'repo');c=Collector()
        self.assertEqual(session_time(root,project,c),'unknown')
        folder=root/'projects'/encode_project(project)
        a=write(folder/'one.jsonl','x');b=write(folder/'two.jsonl','y')
        os.utime(a,(1000,1000));os.utime(b,(2000,2000))
        external=self.tmp/'outside';other=write(external/'secret.jsonl','secret');os.utime(other,(3000,3000))
        make_dir_link(folder/'outside',external)
        self.assertEqual(session_time(root,project,c),'1970-01-01T00:33:20+00:00')

    def test_git_missing_does_not_inspect_parent(self):
        from atlas.scan.state import project_git
        root=self.tmp/'child';root.mkdir();c=Collector()
        with patch('atlas.scan.state.subprocess.run') as run:
            self.assertEqual(project_git(root,c,git='git')['dirtyCount'],'unknown')
            run.assert_not_called()

    def test_session_encoding_collision_does_not_assign_session(self):
        from atlas.scan.state import enrich_state,encode_project
        root=self.tmp/'.claude';a=self.tmp/'a-b';b=self.tmp/'a b'
        a.mkdir();b.mkdir()
        self.assertEqual(encode_project(a),encode_project(b))
        write(root/'projects'/encode_project(a)/'one.jsonl','private')
        cfg=parse_config({'workspaceRoot':str(self.tmp),'skillRoots':[{'path':str(root/'skills'),'profile':'claude','label':'claude'}]})
        c=Collector()
        for p in (a,b):c.add_item(Item(make_id('project',str(p)),'project',p.name,locations=[Location(str(p))]))
        enrich_state(cfg,c)
        self.assertTrue(all(i.metadata['lastSessionAt']=='unknown' for i in c.items.values()))
        self.assertIn('session-path-collision',[w.code for w in c.warnings])

    def test_old_inventory_loads_and_new_hash_is_validated(self):
        inv=Inventory(SCHEMA_VERSION,'now',[self.skill('a','a','max','a'*64)],[],[],False,profiles=['max','pro'])
        data=json.loads(canonical_json(inv));self.assertEqual(inventory_from_dict(data),inv)
        data.pop('profiles');data['items'][0]['locations'][0].pop('contentHash')
        old=inventory_from_dict(data);self.assertEqual(old.profiles,[])
        inv.items[0].locations[0].contentHash='not-hash'
        with self.assertRaises(InventoryError):validate_inventory(inv)

    def test_legacy_inventory_hash_remains_compatible(self):
        import hashlib
        from atlas.model import inventory_hash
        item=Item(make_id('skill','legacy'),'skill','legacy',locations=[Location('legacy','max')])
        inv=Inventory(SCHEMA_VERSION,'now',[item],[],[],False)
        data=json.loads(canonical_json(inv));data.pop('scanned_at')
        data.pop('profiles',None)
        for loc in data['items'][0]['locations']:loc.pop('contentHash',None)
        expected=hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2).encode()).hexdigest()
        self.assertEqual(inventory_hash(inv),expected)

    def test_activity_uses_instant_not_lexicographic_timezone(self):
        from atlas.state import activity_key
        a=Item(make_id('project','a'),'project','a',locations=[Location('a')],metadata={'lastCommitAt':'2026-10-14T10:00:00+02:00'})
        b=Item(make_id('project','b'),'project','b',locations=[Location('b')],metadata={'lastSessionAt':'2026-10-14T09:00:00+00:00'})
        self.assertGreater(activity_key(b),activity_key(a))

    def test_integrated_scan_hashes_locations_and_config_profiles(self):
        from atlas.inventory import build_inventory
        for profile,body in [('max','first'),('pro','second')]:
            write(self.tmp/profile/'skills'/'a'/'SKILL.md',skill_md('a',body))
        cfg=parse_config({'workspaceRoot':str(self.tmp),'skillRoots':[{'path':str(self.tmp/p/'skills'),'profile':p,'label':p} for p in ['max','pro']]})
        inv=build_inventory(cfg).inventory
        self.assertEqual(inv.profiles,['max','pro'])
        self.assertTrue(all(i.metadata['contentStatus']=='razlikuje se' for i in inv.items))

    def test_report_and_catalog_have_state_without_content(self):
        from atlas.report import render_report
        from atlas.catalog import render_catalog
        from atlas.inventory import ScanOutcome
        from atlas.model import inventory_hash
        a=self.skill('same','a','max','a'*64);b=self.skill('same','b','pro','b'*64)
        h=Item(make_id('hook','h'),'hook','Stop',locations=[Location('settings','max',origin='standalone')],metadata={'event':'Stop','hookCount':'1','hookTypes':['command']})
        inv=Inventory(SCHEMA_VERSION,'now',[a,b,h],[],[],False,['max','pro'])
        report=render_report(ScanOutcome(inv,[],0),inventory_hash(inv))
        self.assertIn('Neusklađenost skillova',report)
        self.assertIn('nema u ovom profilu',report)
        html=render_catalog(inv,inventory_hash(inv))
        self.assertIn('id="f-drift"',html)
        self.assertIn('id="atlas-state"',html)


class HashCacheTests(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.root = self.tmp/'skill'
        write(self.root/'SKILL.md', 'prvi sadrzaj')
        write(self.root/'ref/notes.md', 'biljeske')

    def test_unchanged_folder_is_not_read_again(self):
        from pathlib import Path
        from atlas.scan.state import HashCache, content_hash
        cache = HashCache()
        first = content_hash(self.root, Collector(), cache=cache)
        with patch.object(Path, 'open', side_effect=AssertionError('fajl ne smije biti čitan')):
            self.assertEqual(content_hash(self.root, Collector(), cache=cache), first)

    def test_changed_mtime_or_size_recomputes(self):
        from atlas.scan.state import HashCache, content_hash
        cache = HashCache()
        first = content_hash(self.root, Collector(), cache=cache)
        path = self.root/'SKILL.md'
        stamp = path.stat().st_mtime_ns
        path.write_text('drugi sadrzaj', encoding='utf-8')  # ista dužina, drugi sadržaj
        os.utime(path, ns=(stamp + 2_000_000_000, stamp + 2_000_000_000))
        second = content_hash(self.root, Collector(), cache=cache)
        self.assertNotEqual(first, second)
        self.assertEqual(second, content_hash(self.root, Collector()))
        write(self.root/'novo.md', 'x')
        self.assertNotEqual(content_hash(self.root, Collector(), cache=cache), second)

    def test_cache_file_roundtrip_prunes_and_survives_corruption(self):
        from atlas.scan.state import HashCache, content_hash
        path = self.tmp/'data/skill-hash-cache.json'
        cache = HashCache.load(path)
        value = content_hash(self.root, Collector(), cache=cache)
        cache.save()
        again = HashCache.load(path)
        self.assertEqual(content_hash(self.root, Collector(), cache=again), value)
        again.save()
        self.assertEqual(len(json.loads(path.read_text(encoding='utf-8'))['entries']), 1)
        unused = HashCache.load(path)
        unused.save()
        self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['entries'], {})
        path.write_text('{nije json', encoding='utf-8')
        self.assertEqual(content_hash(self.root, Collector(), cache=HashCache.load(path)), value)

    def test_unknown_hash_is_not_cached(self):
        from atlas.scan.state import HashCache, content_hash
        cache = HashCache()
        self.assertEqual(content_hash(self.root, Collector(), cache=cache, max_files=1), 'unknown')
        self.assertEqual(cache.entries, {})

    def test_build_inventory_uses_and_writes_cache(self):
        from atlas.inventory import build_inventory
        home = self.tmp/'home'
        write(home/'.claude/skills/own/SKILL.md', skill_md('own', 'Moj'))
        cfg = parse_config({'workspaceRoot': str(self.tmp/'ws'), 'skillRoots': [
            {'path': str(home/'.claude/skills'), 'profile': 'claude', 'label': '.claude'}]})
        cache_path = self.tmp/'data/skill-hash-cache.json'
        first = build_inventory(cfg, hash_cache_path=cache_path).inventory
        self.assertTrue(cache_path.is_file())
        second = build_inventory(cfg, hash_cache_path=cache_path).inventory
        self.assertEqual([l.contentHash for i in first.items for l in i.locations],
                         [l.contentHash for i in second.items for l in i.locations])
