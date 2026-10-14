import json
import unittest
from pathlib import Path
from unittest.mock import patch

from helpers import TempDirTestCase, make_fixture, write
from test_cli import run
from atlas.paths import AppPaths
from atlas.overlay import Overlay, Note, load_overlay
from atlas.catalog import render_catalog, validate_catalog
from atlas.model import inventory_from_dict, inventory_hash
from atlas.outputs import catalog_target, overlay_target
from atlas.writeout import publish, recover_if_needed


class NotesIntegrationTests(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.app = self.tmp / 'app'
        write(self.app / 'config/sources.local.json', json.dumps(make_fixture(self.tmp)))
        run(['refresh'], self.app)
        self.paths = AppPaths(self.app)
        self.inv = inventory_from_dict(json.loads(self.paths.inventory.read_text(encoding='utf-8')))
        self.id = self.inv.items[0].id

    def note(self, *args):
        return run(['note', self.id, *args], self.app)

    def test_cli_lifecycle_and_refresh(self):
        self.assertEqual(self.note('--text', 'hello', '--tag', 'one')[0], 0)
        self.assertEqual(self.note('--text', 'new')[0], 0)
        self.assertEqual(load_overlay(self.paths.overrides).notes[self.id].tags, ['one'])
        run(['refresh'], self.app)
        self.assertIn('new', self.paths.catalog.read_text(encoding='utf-8'))
        self.assertEqual(self.note('--clear-tags')[0], 0)
        self.assertEqual(load_overlay(self.paths.overrides).notes[self.id].tags, [])
        self.assertEqual(self.note('--delete')[0], 0)
        self.assertEqual(load_overlay(self.paths.overrides).notes, {})

    def test_conflicts_and_invalid_text_preserve_outputs(self):
        self.note('--text', 'old')
        before = [p.read_bytes() for p in (self.paths.overrides, self.paths.catalog)]
        for args in [('--delete', '--text', 'x'), ('--tag', 'x', '--clear-tags'),
                     ('--text', ' '), (), ('--text', 'x'*10001)]:
            with self.subTest(args=args):
                self.assertEqual(self.note(*args)[0], 1)
                self.assertEqual([p.read_bytes() for p in (self.paths.overrides, self.paths.catalog)], before)

    def test_missing_inventory_and_new_note_without_text(self):
        self.assertEqual(self.note('--tag', 'x')[0], 1)
        self.paths.inventory.unlink()
        self.assertEqual(self.note('--text', 'x')[0], 1)
        self.assertFalse(self.paths.overrides.exists())

    def test_parser_errors_return_one_and_help_returns_zero(self):
        for args in [['note'], ['note', self.id, '--text'], ['note', self.id, '--unknown']]:
            with self.subTest(args=args):
                self.assertEqual(run(args, self.app)[0], 1)
        self.assertEqual(run(['note', '--help'], self.app)[0], 0)

    def test_existing_note_rollback_and_committed_cleanup(self):
        import os
        self.note('--text', 'old')
        old = [p.read_bytes() for p in (self.paths.overrides, self.paths.catalog)]
        overlay = Overlay({self.id: Note('new', [])})
        targets = [overlay_target(self.paths, overlay),
                   catalog_target(self.paths, self.inv, inventory_hash(self.inv), overlay)]
        def failing(src, dst):
            if Path(dst) == self.paths.catalog:
                raise KeyboardInterrupt()
            os.replace(src, dst)
        with self.assertRaises(KeyboardInterrupt):
            publish(self.paths, targets, replace=failing)
        self.assertTrue(recover_if_needed(self.paths))
        self.assertEqual([p.read_bytes() for p in (self.paths.overrides, self.paths.catalog)], old)
        with patch('atlas.writeout._discard', side_effect=OSError('cleanup')):
            publish(self.paths, targets)
        self.assertTrue(recover_if_needed(self.paths))
        self.assertEqual(load_overlay(self.paths.overrides).notes[self.id].text, 'new')
        self.assertIn('new', self.paths.catalog.read_text(encoding='utf-8'))

    def test_recovery_rejects_arbitrary_config_target(self):
        from atlas.writeout import RecoveryError
        target = self.paths.config_dir / 'other.json'
        write(target, 'unchanged')
        write(self.paths.journal, json.dumps({'phase':'replace', 'entries':[{
            'target':str(target), 'staged':str(target)+'.abcd.staged', 'backup':None}]}))
        with self.assertRaises(RecoveryError):
            recover_if_needed(self.paths)
        self.assertEqual(target.read_text(), 'unchanged')

    def test_description_change_and_return_reconnect_same_id(self):
        self.note('--text', 'persist')
        data = json.loads(self.paths.inventory.read_text(encoding='utf-8'))
        for item in data['items']:
            if item['id'] == self.id:
                item['description'] = 'changed'
        write(self.paths.inventory, json.dumps(data))
        self.assertEqual(run(['build'], self.app)[0], 0)
        self.assertEqual(load_overlay(self.paths.overrides).notes[self.id].text, 'persist')
        empty = dict(data, items=[], relations=[], warnings=[], partial=False)
        write(self.paths.inventory, json.dumps(empty))
        self.assertEqual(run(['build'], self.app)[0], 0)
        write(self.paths.inventory, json.dumps(data))
        self.assertEqual(run(['build'], self.app)[0], 0)
        self.assertEqual(load_overlay(self.paths.overrides).notes[self.id].text, 'persist')

    def test_unknown_add_orphan_delete_and_bad_overlay(self):
        absent = 'f'*64
        self.assertEqual(run(['note', absent, '--text', 'x'], self.app)[0], 1)
        self.assertEqual(self.note('--text', 'private')[0], 0)
        data = json.loads(self.paths.inventory.read_text(encoding='utf-8'))
        data['items'] = [it for it in data['items'] if it['id'] != self.id]
        data['relations'] = [r for r in data['relations'] if self.id not in (r['source'], r['target'])]
        write(self.paths.inventory, json.dumps(data))
        code, out, _ = run(['build'], self.app)
        self.assertEqual(code, 0)
        self.assertIn('1', out)
        self.assertNotIn(self.id, self.paths.catalog.read_text(encoding='utf-8').split('id="atlas-overlay"')[0])
        self.assertEqual(self.note('--delete')[0], 0)
        before = self.paths.catalog.read_bytes()
        write(self.paths.overrides, '{')
        self.assertEqual(run(['build'], self.app)[0], 1)
        self.assertEqual(self.paths.catalog.read_bytes(), before)

    def test_render_roundtrip_xss_and_validation(self):
        overlay = Overlay({self.id: Note('</script><img src=x onerror=alert(1)>', ['Đurđevak'])})
        h = inventory_hash(self.inv)
        html = render_catalog(self.inv, h, overlay)
        self.assertNotIn('</script><img', html)
        self.assertIn('atlas-overlay', html)
        validate_catalog(html, h)
        with self.assertRaises(ValueError):
            validate_catalog(html.replace('"schemaVersion":1', '"schemaVersion":false'), h)

    def test_publish_failure_and_crash_recover_notes_with_catalog(self):
        import os
        overlay = Overlay({self.id: Note('new', [])})
        original = self.paths.catalog.read_bytes()
        targets = [overlay_target(self.paths, overlay), catalog_target(self.paths, self.inv, inventory_hash(self.inv), overlay)]
        for failure in [OSError('failed'), KeyboardInterrupt()]:
            def replace(src, dst):
                if Path(dst) == self.paths.catalog:
                    raise failure
                os.replace(src, dst)
            try:
                publish(self.paths, targets, replace=replace)
            except (OSError, KeyboardInterrupt):
                pass
            recover_if_needed(self.paths)
            self.assertFalse(self.paths.overrides.exists())
            self.assertEqual(self.paths.catalog.read_bytes(), original)
