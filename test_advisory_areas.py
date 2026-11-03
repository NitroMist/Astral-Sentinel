"""Tests for v0.2.4a affected-area explanations. No external network."""
import unittest
from datetime import datetime, timezone
from engine import affected_areas, snapshot

D = datetime(2026,11,3,1,46,tzinfo=timezone.utc)

class AdvisoryAreaTests(unittest.TestCase):
    def test_strongest_house_first(self):
        aspects = [
            {'transit':'Saturn', 'natal':'Sun', 'house':5, 'nature':'tension', 'value':-0.1},
            {'transit':'Pluto', 'natal':'Saturn', 'house':6, 'nature':'tension', 'value':-2.0},
            {'transit':'Mercury', 'natal':'Venus', 'house':7, 'nature':'support', 'value':1.5},
        ]
        self.assertEqual(affected_areas(aspects,'tension')[0], 'Work & Daily Routines')
        self.assertEqual(affected_areas(aspects,'support')[0], 'Relationships')

    def test_transit_source_topics_secondary(self):
        aspects=[{'transit':'Uranus','natal':'Saturn','house':4,'nature':'tension','value':-1.2}]
        topics=affected_areas(aspects,'tension')
        self.assertEqual(topics[0],'Family & Home')
        self.assertIn('Technology & Change', topics)

    def test_ignores_other_nature_and_zero(self):
        aspects=[{'transit':'Venus','natal':'Venus','house':7,'nature':'support','value':1.5},
                 {'transit':'Mars','natal':'Mars','house':6,'nature':'tension','value':-0.3},
                 {'transit':'Moon','natal':'Moon','house':4,'nature':'tension','value':0}]
        self.assertNotIn('Relationships',affected_areas(aspects,'tension'))
        self.assertEqual(affected_areas(aspects,'mixed'),[])

    def test_snapshot_notices_have_ranked_areas_but_tactical_does_not(self):
        s=snapshot(D)
        cards={n['kind']:n for n in s['notices']}
        for kind in ('tension','support'):
            self.assertGreater(len(cards[kind]['areas']),0)
            self.assertLessEqual(len(cards[kind]['areas']),4)
            self.assertEqual(len(cards[kind]['areas']),len(set(cards[kind]['areas'])))
        self.assertNotIn('areas',cards['neutral'])
        self.assertIsInstance(cards['tension']['areas'][0],str)
        self.assertIsInstance(cards['support']['areas'][0],str)

    def test_visual_orb_does_not_change_area_rankings(self):
        a=snapshot(D,aux_orb=1)
        b=snapshot(D,aux_orb=3)
        self.assertEqual(a['notices'],b['notices'])

    def test_area_rankings_respond_to_enabled_auxiliary_scoring(self):
        a=snapshot(D,aux_scoring=True)
        b=snapshot(D,aux_scoring=False)
        self.assertEqual(a['transit_to_natal_aspects'],b['transit_to_natal_aspects'])
        self.assertEqual(a['notices'][0]['text'],b['notices'][0]['text'])
        self.assertEqual(a['notices'][0]['kind'],b['notices'][0]['kind'])
        self.assertEqual(b['score']['difficulty'],b['score']['planetary_baseline'])
        self.assertEqual(a['score']['planetary_baseline'],b['score']['difficulty'])

if __name__ == '__main__':
    unittest.main()
