"""v1.0.0 release regression checks for local-request policy and metadata."""
import unittest
from pathlib import Path
from datetime import datetime,timezone

import engine
from server import _is_local_request


class ReleaseSafetyTests(unittest.TestCase):
    def test_allowed_local_hosts(self):
        for host in ('127.0.0.1:8765','localhost:8765'):
            self.assertTrue(_is_local_request(host,'',8765))
            self.assertTrue(_is_local_request(host,'http://127.0.0.1:8765',8765))
            self.assertTrue(_is_local_request(host,'http://localhost:8765',8765))

    def test_reject_external_hosts_and_cross_site_origins(self):
        for host in ('', '127.0.0.1', 'localhost', 'attacker.example:8765',
                     '127.0.0.1:8766','127.0.0.1:8765.attacker.example'):
            self.assertFalse(_is_local_request(host,'',8765))
        for origin in ('https://localhost:8765','http://attacker.example',
                       'null','http://127.0.0.1:8765.attacker.example'):
            self.assertFalse(_is_local_request('127.0.0.1:8765',origin,8765))

    def test_release_version_exported(self):
        chart=engine.snapshot(datetime(2026,11,3,1,46,tzinfo=timezone.utc),include_sky=False)
        self.assertEqual(chart['version'],'1.0.0')
        self.assertIn('planetary_baseline',chart['score'])
        self.assertIn('auxiliary_modifier',chart['score'])

    def test_default_profile_contains_no_personal_birth_record(self):
        profile=engine.DEFAULT_PROFILE
        self.assertTrue(profile['label'].startswith('DEMO CHART'))
        self.assertEqual(profile['birth']['date'],'2000-01-01')


if __name__=='__main__':
    unittest.main()
