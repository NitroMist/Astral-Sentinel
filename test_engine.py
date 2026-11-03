"""Astral Sentinel v0.2.3 calculation regression tests."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import swisseph as swe

from engine import (snapshot, forecast, norm_diff, planet_positions,
                    jd_from_utc, angular_separation, chart_at, natal_birth_dt,
                    profile, aspect_phase)

D=datetime(2026,11,2,9,36,tzinfo=timezone.utc)

class CalculationTests(unittest.TestCase):
    def test_tropical_placidus_longitude_default(self):
        snap=snapshot(D)
        self.assertEqual(snap['version'],'1.0.0')
        self.assertEqual(len(snap['transits']),10)
        self.assertEqual(len(snap['heliocentric']),9)
        self.assertEqual(snap['natal']['house_method'],'longitude')
        self.assertTrue(all(1 <= p['house'] <= 12 for p in snap['natal']['positions']))
        self.assertIn(snap['verification']['status'],('unavailable','review','match'))
        self.assertEqual(snap['birth_profile']['label'],profile()['label'])

    def test_3d_placidus_explicit_alternative(self):
        snap=snapshot(D,house_method='spatial')
        h={p['name']:p['house'] for p in snap['natal']['positions']}
        self.assertTrue(all(1 <= house <= 12 for house in h.values()))
        self.assertEqual(snap['natal']['house_method'],'spatial')
        self.assertEqual(snap['natal']['angles']['Ascendant'],snapshot(D)['natal']['angles']['Ascendant'])

    def test_all_house_and_zodiac_modes(self):
        for house in ('placidus','whole','equal'):
            for zodiac in ('tropical','sidereal_lahiri'):
                for method in ('longitude','spatial'):
                    with self.subTest(house=house,zodiac=zodiac,method=method):
                        snap=snapshot(D,house,zodiac,house_method=method)
                        self.assertEqual(snap['natal']['house_system'],house)
                        self.assertEqual(snap['natal']['zodiac'],zodiac)
                        self.assertEqual(snap['natal']['house_method'],method)
                        self.assertTrue(all(1<=p['house']<=12 for p in snap['natal']['positions']))

    def test_13_entry_cusp_fork_compatibility(self):
        original=swe.houses_ex
        def mocked(*args,**kwargs):
            cusps,angles=original(*args,**kwargs)
            return ((0.0,)+tuple(cusps),angles)
        with patch.object(swe,'houses_ex',side_effect=mocked):
            snap=snapshot(D)
        self.assertEqual(len(snap['natal']['cusps']),12)
        self.assertAlmostEqual(snap['natal']['angles']['Ascendant'],snapshot(D)['natal']['angles']['Ascendant'],places=4)

    def test_moon_like_fast_mover_approaches_then_separates(self):
        # Synthetic geometry exercises the near-exact Moon issue without a real person's chart.
        self.assertEqual(aspect_phase(279.9, 13.8, 100.0, 180.0, 0.1),'applying')
        self.assertEqual(aspect_phase(280.1, 13.8, 100.0, 180.0, 0.1),'separating')

    def test_near_exact_aspect(self):
        self.assertEqual(aspect_phase(100,1,100,0,0),'exact')

    def test_heliocentric_and_geocentric_differ(self):
        s=snapshot(D)
        g=next(p['longitude'] for p in s['transits'] if p['name']=='Mars')
        h=next(p['longitude'] for p in s['heliocentric'] if p['name']=='Mars')
        self.assertGreater(abs(norm_diff(g,h)),1)

    def test_forecast_modes_and_sampling(self):
        for days,step in ((7,3),(30,6),(90,12)):
            with self.subTest(days=days):
                f=forecast(D,days,house_method='longitude')
                self.assertEqual(f['sampling_hours'],step)
                self.assertEqual(len(f['samples']),1+24*days//step)
                self.assertLessEqual(f['lowest']['difficulty'],f['highest']['difficulty'])
                self.assertEqual(f['house_method'],'longitude')
                self.assertEqual(f['start_utc'],D.isoformat())

    def test_local_birth_clock_resolves_without_overriding_profile(self):
        from profile_manager import birth_utc
        p=profile()
        self.assertEqual(natal_birth_dt(p),birth_utc(p['birth']))
        self.assertEqual(snapshot(D)['natal']['timestamp'],birth_utc(p['birth']).isoformat())

    def test_mean_nodes_lilith_and_fortune(self):
        snap=snapshot(D)
        natal={p['name']:p for p in snap['natal']['auxiliary_points']}
        current={p['name']:p for p in snap['auxiliary_transits']}
        jd=jd_from_utc(natal_birth_dt(profile()))
        self.assertAlmostEqual(natal['North Node']['longitude'],swe.calc_ut(jd,swe.MEAN_NODE,swe.FLG_MOSEPH)[0][0],places=3)
        self.assertAlmostEqual(natal['Black Moon Lilith']['longitude'],swe.calc_ut(jd,swe.MEAN_APOG,swe.FLG_MOSEPH)[0][0],places=3)
        self.assertTrue(0<=natal['Part of Fortune']['longitude']<360)
        self.assertAlmostEqual((natal['South Node']['longitude']-natal['North Node']['longitude'])%360,180,places=5)
        self.assertAlmostEqual((current['South Node']['longitude']-current['North Node']['longitude'])%360,180,places=5)
        self.assertIn('Vertex',natal)
        self.assertNotIn('Part of Fortune',current)
        self.assertNotIn('Vertex',current)
        self.assertTrue(snap['auxiliary_meta']['aspects_scored'])

    def test_node_and_lilith_modes_and_score_unchanged(self):
        mean=snapshot(D)
        changed=snapshot(D,node_mode='true',lilith_mode='osculating')
        self.assertEqual(mean['score']['planetary_baseline'],changed['score']['planetary_baseline'])
        self.assertEqual(mean['transit_to_natal_aspects'],changed['transit_to_natal_aspects'])
        a={p['name']:p for p in mean['auxiliary_transits']}
        b={p['name']:p for p in changed['auxiliary_transits']}
        self.assertGreater(abs(norm_diff(a['North Node']['longitude'],b['North Node']['longitude'])),.01)
        self.assertGreater(abs(norm_diff(a['Black Moon Lilith']['longitude'],b['Black Moon Lilith']['longitude'])),1)
        self.assertEqual(b['North Node']['method'],'true')
        self.assertEqual(b['Black Moon Lilith']['method'],'osculating')

    def test_auxiliary_house_modes_and_sidereal(self):
        for system in ('placidus','whole','equal'):
            for zodiac in ('tropical','sidereal_lahiri'):
                snap=snapshot(D,system,zodiac)
                self.assertTrue(all(1<=p['house']<=12 for p in snap['natal']['auxiliary_points']))
                # Optional Chiron is available when seas_18.se1 is installed.
                expected = 6 if (snap['natal']['auxiliary_unavailable'] == [] and any(p['name']=='Chiron' for p in snap['natal']['auxiliary_points'])) else 5
                self.assertEqual(len(snap['natal']['auxiliary_points']), expected)

    def test_missing_chiron_file_is_nonfatal(self):
        snap=snapshot(D)
        names={p['name'] for p in snap['auxiliary_transits']}
        if 'Chiron' not in names:
            self.assertTrue(any(p['name']=='Chiron' for p in snap['auxiliary_unavailable']))

    def test_chiron_ephemeris_file_enables_natal_transit_aspects_and_scoring(self):
        from engine import ROOT, AUX_SCORING_WEIGHTS, auxiliary_positions
        import math
        ephe=ROOT/'ephe'/'seas_18.se1'
        self.assertTrue(ephe.is_file(), 'Chiron data pack missing seas_18.se1')
        dt=datetime(2026,11,3,1,46,23,tzinfo=timezone.utc)
        snap=snapshot(dt)
        natal={p['name']:p for p in snap['natal']['auxiliary_points']}
        transits={p['name']:p for p in snap['auxiliary_transits']}
        self.assertIn('Chiron',natal)
        self.assertIn('Chiron',transits)
        self.assertFalse(any(p['name']=='Chiron' for p in snap['auxiliary_unavailable']))
        self.assertFalse(any(p['name']=='Chiron' for p in snap['natal']['auxiliary_unavailable']))
        jd=jd_from_utc(natal_birth_dt(profile()))
        swe.set_ephe_path(str(ephe.parent))
        self.assertAlmostEqual(natal['Chiron']['longitude'],swe.calc_ut(jd,swe.CHIRON,swe.FLG_SWIEPH)[0][0],places=4)
        self.assertAlmostEqual(transits['Chiron']['longitude'],27.9800298,places=4)
        self.assertTrue(transits['Chiron']['retrograde'])
        self.assertTrue(1<=natal['Chiron']['house']<=12)
        self.assertAlmostEqual(AUX_SCORING_WEIGHTS['Chiron'], .38)
        chiron_aspects=[a for a in snap['auxiliary_aspects']+snap['auxiliary_sky_aspects'] if 'Chiron' in (a['source'],a['target'])]
        self.assertGreater(len(chiron_aspects),0)
        self.assertTrue(all(a['orb']<=2 for a in chiron_aspects))
        self.assertIsInstance(snap['auxiliary_scoring']['entries'],list)
        self.assertEqual(snap['score']['planetary_baseline'],snapshot(dt,aux_scoring=False)['score']['difficulty'])
        f=forecast(dt,7)
        self.assertEqual(f['samples'][0]['difficulty'],snap['score']['difficulty'])
        self.assertEqual(f['samples'][0]['auxiliary_modifier'],snap['score']['auxiliary_modifier'])

    def test_invalid_auxiliary_modes(self):
        with self.assertRaises(ValueError): snapshot(D,node_mode='invalid')
        with self.assertRaises(ValueError): snapshot(D,lilith_mode='invalid')

    def test_auxiliary_lines_are_true_major_aspects_and_unscored(self):
        from engine import angular_separation
        snap=snapshot(D)
        self.assertEqual(snap['auxiliary_meta']['aspect_orb'],2.0)
        self.assertGreater(len(snap['auxiliary_aspects']),0)
        self.assertGreater(len(snap['auxiliary_sky_aspects']),0)
        by_transit={p['name']:p for p in snap['transits']}
        by_aux_transit={p['name']:p for p in snap['auxiliary_transits']}
        by_natal={p['name']:p for p in snap['natal']['positions']+snap['natal']['auxiliary_points']}
        by_natal.update({'Ascendant':{'longitude':snap['natal']['angles']['Ascendant']},
                         'Midheaven':{'longitude':snap['natal']['angles']['Midheaven']}})
        for a in snap['auxiliary_aspects'] + snap['auxiliary_sky_aspects']:
            source=(by_aux_transit if a['source_auxiliary'] else by_transit)[a['source']]
            if a['target_scope']=='natal':
                target=by_natal[a['target']]
            else:
                target=by_transit[a['target']]
            orb=abs(angular_separation(source['longitude'],target['longitude'])-a['angle'])
            self.assertAlmostEqual(orb,a['orb'],places=3)
            self.assertLessEqual(a['orb'],2)
            self.assertFalse(a['scored'])
            self.assertIn(a['type'],('trine','sextile','conjunction','opposition','square'))
        self.assertTrue(all(a['target_scope']=='natal' for a in snap['auxiliary_aspects']))

    def test_auxiliary_aspect_orb_filter_works_and_does_not_change_scores(self):
        tight=snapshot(D,aux_orb=1)
        wide=snapshot(D,aux_orb=3)
        for key in ('score','planet_status','transit_to_natal_aspects','notices'):
            self.assertEqual(tight[key],wide[key])
        self.assertLessEqual(len(tight['auxiliary_aspects']),len(wide['auxiliary_aspects']))
        self.assertLessEqual(len(tight['auxiliary_sky_aspects']),len(wide['auxiliary_sky_aspects']))
        self.assertTrue(all(a['orb'] <= 1 for a in tight['auxiliary_aspects']))

    def test_auxiliary_aspects_independent_of_house_system_and_obey_node_mode(self):
        a=snapshot(D,node_mode='mean',lilith_mode='mean')
        b=snapshot(D,house_system='whole')
        pairs=lambda s:{(x['source'],x['target'],x['type']) for x in s['auxiliary_aspects']}
        self.assertEqual(pairs(a),pairs(b))
        c=snapshot(D,node_mode='true',lilith_mode='osculating')
        self.assertEqual(a['score']['planetary_baseline'],c['score']['planetary_baseline'])
        self.assertNotEqual(pairs(a),pairs(c))

    def test_invalid_auxiliary_orbs_rejected(self):
        for orb in (0, -1, 3.1, float('inf'), float('nan')):
            with self.subTest(orb=orb),self.assertRaises(ValueError):
                snapshot(D,aux_orb=orb)

    def test_invalid_house_method_rejected(self):
        with self.assertRaises(ValueError): snapshot(D,house_method='invalid')
        with self.assertRaises(ValueError): forecast(D,house_method='invalid')

if __name__=='__main__': unittest.main()

class AuxiliaryScoringTests(unittest.TestCase):
    def test_toggle_restores_original_score(self):
        from engine import compute_score
        enabled=snapshot(D,aux_scoring=True)
        disabled=snapshot(D,aux_scoring=False)
        self.assertEqual(disabled['score']['difficulty'],compute_score(disabled['transit_to_natal_aspects'])['difficulty'])
        self.assertEqual(enabled['score']['planetary_baseline'],disabled['score']['difficulty'])
        self.assertEqual(disabled['auxiliary_scoring']['modifier'],0)
        self.assertLessEqual(abs(enabled['auxiliary_scoring']['modifier']),.65)
    def test_visual_orb_does_not_affect_scoring(self):
        a=snapshot(D,aux_orb=1);b=snapshot(D,aux_orb=3)
        self.assertEqual(a['score'],b['score'])
        self.assertEqual(a['auxiliary_scoring'],b['auxiliary_scoring'])
    def test_node_axis_not_double_counted(self):
        from engine import auxiliary_influence
        data=snapshot(D)['auxiliary_scoring']['entries']
        axes=[(a['source'] if a['source'] not in ('North Node','South Node') else 'axis',
               a['target'] if a['target'] not in ('North Node','South Node') else 'axis', a['category']) for a in data]
        self.assertEqual(len(axes),len(set(axes)))
    def test_forecast_and_snapshot_share_scoring(self):
        for enabled in (True,False):
            snap=snapshot(D,aux_scoring=enabled)
            f=forecast(D,7,aux_scoring=enabled)
            self.assertEqual(f['samples'][0]['difficulty'],snap['score']['difficulty'])
            self.assertEqual(f['samples'][0]['auxiliary_modifier'],snap['score']['auxiliary_modifier'])

if __name__=='__main__':
    unittest.main()
