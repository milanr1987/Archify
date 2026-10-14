import json
import tempfile
import unittest
from pathlib import Path

from atlas.overlay import (Overlay, OverlayError, Note, load_overlay,
                           overlay_from_dict, canonical_overlay, update_note)

ID = 'a' * 64


class OverlayTests(unittest.TestCase):
    def test_roundtrip_and_updates_preserve_tags(self):
        one = update_note(Overlay({}), ID, text=' hello ', tags=[' x ', 'x'])
        self.assertEqual(one.notes[ID], Note('hello', ['x']))
        two = update_note(one, ID, text='new')
        self.assertEqual(two.notes[ID].tags, ['x'])
        self.assertEqual(one.notes[ID].text, 'hello')
        self.assertEqual(overlay_from_dict(json.loads(canonical_overlay(two))), two)
        self.assertEqual(update_note(two, ID, tags=[]).notes[ID].tags, [])
        self.assertEqual(update_note(two, ID, delete=True).notes, {})

    def test_missing_file_and_size_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'overlay.json'
            self.assertEqual(load_overlay(p), Overlay({}))
            valid = b'{"schemaVersion":1,"notes":{}}'
            p.write_bytes(valid + b' ' * (1024 * 1024 - len(valid)))
            self.assertEqual(load_overlay(p), Overlay({}))
            p.write_bytes(b' ' * (1024 * 1024))
            with self.assertRaises(OverlayError):
                load_overlay(p)
            p.write_bytes(b' ' * (1024 * 1024 + 1))
            with self.assertRaises(OverlayError):
                load_overlay(p)

    def test_invalid_schema_values(self):
        values = [None, {}, {'schemaVersion': True, 'notes': {}},
                  {'schemaVersion': 1, 'notes': {}, 'secret': 1}]
        for value in values:
            with self.subTest(value=value), self.assertRaises(OverlayError):
                overlay_from_dict(value)
        for value in [True, [], 1, '', ' ']:
            with self.subTest(text=value), self.assertRaises(OverlayError):
                update_note(Overlay({}), ID, text=value)

    def test_text_tag_and_id_limits(self):
        update_note(Overlay({}), ID.upper(), text='x'*10000, tags=['x'*100])
        update_note(Overlay({}), ID, text='x', tags=[str(i) for i in range(20)])
        for kw in [dict(text='x'*10001), dict(text='x', tags=['x'*101]),
                   dict(text='x', tags=[str(i) for i in range(21)]),
                   dict(text='x', tags=[True]), dict(text='x', tags=[' '])]:
            with self.subTest(kw=kw), self.assertRaises(OverlayError):
                update_note(Overlay({}), ID, **kw)
        with self.assertRaises(OverlayError):
            update_note(Overlay({}), 'bad', text='x')
        with self.assertRaises(OverlayError):
            overlay_from_dict({'schemaVersion': 1, 'notes': {
                ID: {'text': 'x', 'tags': []}, ID.upper(): {'text':'y','tags':[]}}})

    def test_new_note_requires_text_and_unknown_fields_rejected(self):
        with self.assertRaises(OverlayError):
            update_note(Overlay({}), ID, tags=['x'])
        with self.assertRaises(OverlayError):
            overlay_from_dict({'schemaVersion':1,'notes':{
                ID:{'text':'x','tags':[],'extra':1}}})
