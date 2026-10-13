import json, unittest
from pathlib import Path
from unittest import mock
from helpers import TempDirTestCase, write, make_dir_link, skill_md
from atlas.config import parse_config, allowed_roots
from atlas.scan.collector import Collector
from atlas.scan.projects import scan_projects
from atlas.scan.skills import scan_skills, SkillReader
from atlas.identity import make_id
from atlas.model import inventory_from_dict, InventoryError, canonical_json, Inventory, Item, Location

class ReviewRegressionTests(TempDirTestCase):
    def test_project_alias_preserves_both_logical_locations(self):
        workspace=self.tmp/'ws'; real=workspace/'real'
        write(real/'package.json',json.dumps({'name':'demo'}))
        make_dir_link(workspace/'alias',real)
        c=Collector(); scan_projects(parse_config({'workspaceRoot':str(workspace),'projectRoots':['.']}),c)
        projects=[i for i in c.items.values() if i.kind=='project']
        self.assertEqual(len(projects),1)
        self.assertEqual({Path(l.path).name for l in projects[0].locations},{'real','alias'})

    def test_invalid_inventory_fields_raise_inventory_error(self):
        inv=Inventory(1,'2026-10-13', [Item(make_id('skill','a'),'skill','a',locations=[Location('C:/a')])],[],[],False)
        for field,value in (('id',[]),('kind',{}),('locations',123)):
            with self.subTest(field=field):
                data=json.loads(canonical_json(inv));data['items'][0][field]=value
                with self.assertRaises(InventoryError):inventory_from_dict(data)

    def test_limit_stops_reading_new_skill_sources(self):
        workspace=self.tmp/'ws'; skills=workspace/'skills'
        for n in range(5):write(skills/str(n)/'SKILL.md',skill_md(str(n),'description'))
        config=parse_config({'workspaceRoot':str(workspace),'skillRoots':[{'path':str(skills),'profile':'x','label':'x'}]})
        c=Collector(max_items=1);reader=SkillReader(c)
        with mock.patch.object(reader,'read',wraps=reader.read) as read:
            scan_skills(config,c,reader,allowed_roots(config))
        self.assertEqual(len(c.items),1)
        self.assertEqual(read.call_count,1)
        self.assertTrue(c.limit_hit)
