import hashlib
import json
import unittest
from unittest.mock import patch
from helpers import TempDirTestCase, write, make_dir_link
from atlas.maps import validate_analysis, source_fingerprint, map_status, load_registry, render_map, MapError, bounded_json
from atlas.cli import main
from atlas.model import Inventory, Item, Location, SCHEMA_VERSION, canonical_json
from atlas.paths import AppPaths


class MapTests(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.source = write(self.tmp / 'src/main.py', 'print(1)')
        self.analysis = {'schemaVersion':1,'projectId':'a'*64,'projectRoot':str(self.tmp),
            'generatedAt':'2026-10-14T00:00:00+02:00','components':[
                {'id':'cli','name':'CLI','purpose':'entry','evidenceIds':['main']}],
            'edges':[], 'evidence':[{'id':'main','relativePath':'src/main.py','line':1,
                'fileHash':hashlib.sha256(self.source.read_bytes()).hexdigest()}], 'openQuestions':[]}

    def test_current_changed_missing_and_incomplete(self):
        validate_analysis(self.analysis)
        self.assertEqual(map_status(self.analysis), 'current')
        initial = source_fingerprint(self.analysis)
        self.source.write_text('changed')
        self.assertEqual(map_status(self.analysis), 'stale')
        self.source.unlink()
        self.assertEqual(map_status(self.analysis), 'stale')
        self.analysis['evidence'] = []
        self.analysis['components'][0]['evidenceIds'] = []
        self.assertEqual(map_status(self.analysis), 'unverified')
        self.assertNotEqual(source_fingerprint(self.analysis), initial)

    def test_invalid_paths_and_references(self):
        for relative in ['../outside.py', str(self.source), '.env', '.codex/auth.json']:
            value = json.loads(json.dumps(self.analysis))
            value['evidence'][0]['relativePath'] = relative
            with self.subTest(relative=relative), self.assertRaises(MapError):
                validate_analysis(value)
        self.analysis['components'][0]['evidenceIds'] = ['unknown']
        with self.assertRaises(MapError): validate_analysis(self.analysis)

    def test_fingerprint_ignores_time(self):
        value = source_fingerprint(self.analysis)
        self.analysis['generatedAt'] = '2026-10-15T00:00:00+02:00'
        self.assertEqual(source_fingerprint(self.analysis), value)

    def test_malformed_edge_and_unavailable_line(self):
        self.analysis['edges'] = [{'from':[],'to':'cli','label':'x','status':'observed','evidenceIds':['main']}]
        with self.assertRaises(MapError): validate_analysis(self.analysis)
        self.analysis['edges'] = []
        self.analysis['evidence'][0]['line'] = 1000
        self.assertEqual(map_status(self.analysis),'unverified')

    def test_map_publish_crash_rolls_back_whole_set(self):
        import os
        from atlas.writeout import publish, Target, recover_if_needed
        paths = AppPaths(self.tmp)
        files = [paths.data_dir/'analysis/demo.json', paths.data_dir/'maps/demo.json',
                 paths.output_dir/'maps/demo.html',paths.map_registry,paths.catalog]
        for file in files: write(file, 'OLD')
        targets = [Target(file,'NEW',lambda text: None) for file in files]
        def failing(src, dst):
            if str(dst) == str(paths.map_registry):
                raise KeyboardInterrupt()
            os.replace(src,dst)
        with self.assertRaises(KeyboardInterrupt): publish(paths,targets,replace=failing)
        self.assertTrue(recover_if_needed(paths))
        self.assertEqual([file.read_text() for file in files],['OLD']*5)

    def test_legacy_current_config_is_ignored(self):
        paths = AppPaths(self.tmp)
        write(paths.default_config,'{')
        write(paths.config_dir/'sources.current.json',json.dumps({'workspaceRoot':str(self.tmp)}))
        self.assertEqual(main(['scan'],app_root=self.tmp),1)
        self.assertEqual(main(['scan','--config','config/sources.current.json'],app_root=self.tmp),0)

    def test_registry_rejects_unsafe_links(self):
        path = self.tmp / 'registry.json'
        self.assertEqual(load_registry(path), [])
        for link in ['../escape.html','https://evil.test/x','maps/x.html/other']:
            write(path, json.dumps({'schemaVersion':1,'maps':[{
                'projectId':'a'*64,'title':'demo','htmlPath':link,'analysisPath':'analysis/demo.json',
                'generatedAt':self.analysis['generatedAt'], 'sourceFingerprint':'b'*64}]}))
            with self.assertRaises(MapError): load_registry(path)

    def test_large_serialized_output_and_private_junction(self):
        with self.assertRaises(MapError): bounded_json({'text':'x'*1048577})
        self.assertLessEqual(len(bounded_json(self.analysis).encode('utf-8')),1048576)
        private = self.tmp/'.private'
        write(private/'main.py','synthetic private fixture')
        make_dir_link(self.tmp/'public',private)
        self.analysis['evidence'][0]['relativePath'] = 'public/main.py'
        with self.assertRaises(MapError): validate_analysis(self.analysis)

    def test_adapter_list_arguments_and_failure_preserves_output(self):
        output = write(self.tmp / 'old map.html','OLD')
        source = write(self.tmp / 'input with spaces.json','{}')
        with patch('atlas.maps.subprocess.run') as run:
            run.return_value.returncode = 1
            with self.assertRaises(MapError):
                render_map(self.tmp, 'workflow', source, output)
            args = run.call_args[0][0]
            self.assertIsInstance(args, list)
            self.assertIn(str(source), args)
            self.assertFalse(run.call_args.kwargs.get('shell', False))
            self.assertEqual(run.call_args.kwargs['env']['ARCHIFY_UPDATE_CHECK_DISABLED'], '1')
            self.assertEqual(output.read_text(), 'OLD')

    def test_cli_registers_map_and_build_refreshes_status(self):
        paths = AppPaths(self.tmp)
        inv = Inventory(SCHEMA_VERSION,self.analysis['generatedAt'],[
            Item('a'*64,'project','demo','',[Location(str(self.tmp))])],[],[],False)
        write(paths.inventory, canonical_json(inv))
        analysis = write(self.tmp/'input-analysis.json',json.dumps(self.analysis))
        native = write(self.tmp/'native.json',json.dumps({'meta':{'title':'Demo'}}))
        args = ['map','a'*64,'--analysis',str(analysis),'--input',str(native),'--slug','demo']
        with patch('atlas.mapops.render_map', return_value='<html><svg></svg></html>'):
            self.assertEqual(main(args, app_root=self.tmp), 0)
        self.assertEqual(load_registry(paths.map_registry)[0]['htmlPath'], 'maps/demo.html')
        html = paths.catalog.read_text(encoding='utf-8')
        self.assertIn('atlas-maps', html)
        self.assertIn('"status":"current"', html)
        self.source.write_text('changed')
        self.assertEqual(main(['build'], app_root=self.tmp), 0)
        self.assertIn('"status":"stale"',paths.catalog.read_text(encoding='utf-8'))
        previous = [p.read_bytes() for p in (paths.map_registry,paths.output_dir/'maps/demo.html')]
        with patch('atlas.mapops.render_map',side_effect=MapError('failed')):
            self.assertEqual(main(args,app_root=self.tmp),1)
        self.assertEqual([p.read_bytes() for p in (paths.map_registry,paths.output_dir/'maps/demo.html')], previous)
