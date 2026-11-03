"""Regression tests for the private journal and Joplin handoff."""
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch

from engine import snapshot
from observation_log import (create_entry, delete_entry, read_log, one_entry,
                             markdown_all, markdown_entry, send_to_joplin)


class ObservationLogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.payload = {
            'date': '2026-11-02',
            'observed_difficulty': 4,
            'note': 'Finished a model, slept well.',
            'chart_at_utc': '2026-11-02T18:00:00+00:00',
            'options': {'house': 'placidus', 'house_method': 'longitude',
                        'zodiac': 'tropical', 'node_mode': 'mean',
                        'lilith_mode': 'mean', 'aux_scoring': True},
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_recalculate_save_and_export(self):
        entry = create_entry(self.root, self.payload, snapshot)
        self.assertAlmostEqual(entry['predicted_difficulty'], snapshot(datetime(2026, 11, 2, 18, tzinfo=timezone.utc))['score']['difficulty'])
        self.assertEqual(read_log(self.root)[0]['id'], entry['id'])
        self.assertIn('Finished a model', markdown_entry(entry))
        self.assertIn('Observation Log', markdown_all(read_log(self.root)))
        self.assertNotIn('token', (self.root / 'data' / 'observations.json').read_text())

    def test_delete_only_local_entry(self):
        a = create_entry(self.root, self.payload, snapshot)
        b = create_entry(self.root, self.payload, snapshot)
        self.assertTrue(delete_entry(self.root, a['id']))
        self.assertEqual([x['id'] for x in read_log(self.root)], [b['id']])
        self.assertFalse(delete_entry(self.root, a['id']))

    def test_validation_no_corrupt_file(self):
        for change in ({'note': ''}, {'date': '2026-02-30'}, {'observed_difficulty': 11}, {'chart_at_utc': 'not-date'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                create_entry(self.root, {**self.payload, **change}, snapshot)
        self.assertEqual(read_log(self.root), [])

    def test_joplin_explicit_creation_and_duplicate_guard(self):
        entry = create_entry(self.root, self.payload, snapshot)
        call_log = []
        def fake_joplin(port, route, token=None, payload=None):
            call_log.append((port, route, token, payload))
            if route == '/ping': return 'JoplinClipperServer'
            if route.startswith('/folders?'): return {'items': [], 'has_more': False}
            if route == '/folders': return {'id': 'folder123'}
            if route == '/notes': return {'id': 'note123'}
            raise AssertionError(route)
        with patch('observation_log._joplin', side_effect=fake_joplin):
            result = send_to_joplin(self.root, entry['id'], 'testingtoken123456', 41184)
            self.assertEqual(result['note_id'], 'note123')
            with self.assertRaisesRegex(ValueError, 'Already sent'):
                send_to_joplin(self.root, entry['id'], 'testingtoken123456', 41184)
        self.assertEqual(len([x for x in call_log if x[1] == '/notes']), 1)
        body = next(x[3] for x in call_log if x[1] == '/notes')
        self.assertIn('Finished a model', body['body'])
        self.assertNotIn('testingtoken123456', (self.root / 'data' / 'observations.json').read_text())
        self.assertEqual(one_entry(self.root, entry['id'])['joplin_note_id'], 'note123')


if __name__ == '__main__': unittest.main()
