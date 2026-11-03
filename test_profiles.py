"""Regression tests for v1.0.0 multi-profile chart management."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import engine
from profile_manager import (read_library,create_profile,update_profile,delete_profile,
    export_profile,import_profile,switch_profile,birth_utc,validate_profile,get_active_profile)
from city_lookup import search_cities


def sample(label='New Reader',time='08:10',date='2001-06-21',zone='America/Los_Angeles'):
    return {'label':label,'birth':{'date':date,'time':time,'timezone':zone,
                                 'latitude':47.6062,'longitude':-122.3321,
                                 'location_label':'Seattle, US'},
            'default_house_system':'placidus','default_zodiac':'tropical'}


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        (self.root/'data').mkdir()
        (self.root/'data'/'profile.json').write_text(json.dumps(engine.DEFAULT_PROFILE))

    def test_legacy_profile_read_only_until_create(self):
        old=(self.root/'data'/'profile.json').read_bytes()
        lib=read_library(self.root)
        self.assertEqual(lib['active_id'],'original')
        self.assertEqual(lib['profiles'][0]['birth']['timezone'],'Europe/London')
        self.assertFalse((self.root/'data'/'profiles.json').exists())
        create_profile(self.root,sample())
        self.assertEqual((self.root/'data'/'profile.json').read_bytes(),old)

    def test_save_switch_and_recalculate_different_natal_chart(self):
        at=datetime(2026,11,3,0,tzinfo=timezone.utc)
        with patch.object(engine,'ROOT',self.root):
            prior=engine.snapshot(at,include_sky=False)
            profile=sample('London Birth','12:00','2001-03-04','Europe/London')
            profile['birth'].update(latitude=51.5085,longitude=-0.1257,location_label='London, GB')
            created=create_profile(self.root,profile)
            current=engine.snapshot(at,include_sky=False)
            self.assertEqual(current['birth_profile']['label'],'London Birth')
            self.assertNotAlmostEqual(prior['natal']['angles']['Ascendant'],current['natal']['angles']['Ascendant'],places=1)
            self.assertEqual(current['verification']['status'],'unavailable')
            self.assertIn('No external PDF',current['verification']['message'])
            switch_profile(self.root,'original')
            after=engine.snapshot(at,include_sky=False)
            self.assertEqual(after['natal']['angles'],prior['natal']['angles'])
            self.assertEqual(after['score'],prior['score'])
            self.assertEqual(created['profile']['id'],current['birth_profile']['id'])

    def test_birth_clock_daylight_saving_nonexistent_and_ambiguous(self):
        with self.assertRaisesRegex(ValueError,'did not exist'):
            validate_profile(sample(time='02:30',date='2026-03-08'))
        with self.assertRaisesRegex(ValueError,'occurred twice'):
            validate_profile(sample(time='01:30',date='2026-11-01'))
        p=sample(time='01:30',date='2026-11-01')
        p['birth']['fold']=0
        t0=birth_utc(p['birth']);p['birth']['fold']=1;t1=birth_utc(p['birth'])
        self.assertEqual((t1-t0).total_seconds(),3600)
        p['birth']['date']='2026-03-08';p['birth']['time']='03:30'
        self.assertIsNotNone(birth_utc(p['birth']))

    def test_json_portable_and_delete(self):
        p=create_profile(self.root,sample())
        file=export_profile(self.root,p['active_id'])
        self.assertEqual(file['format'],'astral-sentinel-birth-profile')
        self.assertNotIn('reference_pdf',file['profile'])
        self.assertNotIn('id',file['profile'])
        duplicate=import_profile(self.root,file)
        self.assertNotEqual(duplicate['active_id'],p['active_id'])
        self.assertEqual(len(read_library(self.root)['profiles']),3)
        delete_profile(self.root,duplicate['active_id'])
        delete_profile(self.root,p['active_id'])
        self.assertEqual(read_library(self.root)['active_id'],'original')
        with self.assertRaisesRegex(ValueError,'at least one'):
            delete_profile(self.root,'original')

    def test_reject_malformed_untrusted_import_without_touching_registry(self):
        cases=[{}, {'format':'astral-sentinel-birth-profile','version':1,'profile':{'label':'X','birth':{}}},
               {'birth_profile':{'label':'X','birth':{'date':'not-a-date'}}}]
        before=read_library(self.root)
        for case in cases:
            with self.assertRaises(ValueError):import_profile(self.root,case)
        self.assertEqual(read_library(self.root),before)
        self.assertFalse((self.root/'data'/'profiles.json').exists())

    def test_edit_original_away_from_reference_disables_pdf_comparison(self):
        changed=sample('Updated Original')
        changed['birth']['time']='08:30'
        update_profile(self.root,'original',changed)
        self.assertFalse(get_active_profile(self.root).get('reference_pdf'))

    def test_offline_city_lookup(self):
        ventura=search_cities('ventura')
        self.assertTrue(ventura)
        self.assertEqual(ventura[0]['timezone'],'America/Los_Angeles')
        self.assertEqual(ventura[0]['country'],'US')
        self.assertEqual(search_cities('z'),[])
        self.assertTrue(search_cities('mexico city'))


if __name__=='__main__':unittest.main()
