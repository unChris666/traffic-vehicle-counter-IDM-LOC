from copy import deepcopy
import json
from pathlib import Path
import unittest

from location_intelligent_capacity import estimate_capacity
from location_intelligent_config import get_config


class CapacityTests(unittest.TestCase):
    def setUp(self):
        p = Path(__file__).resolve().parents[1] / 'docs/evidence/location_intelligent/li01_20261022/li1_fixture_result.json'
        self.selection = json.loads(p.read_text())

    def sample(self, kind, area=100, **props):
        b = deepcopy(self.selection['selected'][0])
        b.update(building_type=kind, area_m2=area, raw_properties=props)
        self.selection['selected'] = [b]
        return estimate_capacity(self.selection)

    def test_standard_unit_not_invented(self):
        r = self.sample('standard_residential')
        self.assertEqual(r['rows'][0]['capacity_reference_rounded'], 4)
        self.assertIn('UNRESOLVED', r['rows'][0]['unit'])
        self.assertIsNone(r['mixed_unit_total'])

    def test_apartment_fractional_then_reference_round(self):
        r = self.sample('apartment', 450, num_floors=2)
        self.assertEqual(r['rows'][0]['capacity_reference_rounded'], 10)
        self.assertAlmostEqual(r['rows'][0]['capacity_unrounded'], 9.8)

    def test_dormitory_rooms(self):
        r = self.sample('dormitory', 300, num_floors=2)
        self.assertEqual(r['rows'][0]['capacity_reference_rounded'], 21)
        self.assertEqual(r['rows'][0]['unit'], 'OCCUPIED_ROOMS_ESTIMATED')

    def test_hotel_guests_separate(self):
        r = self.sample('hotel', 300, num_floors=2)
        self.assertAlmostEqual(r['rows'][0]['capacity_unrounded'], 11.7)
        self.assertEqual(r['rows'][0]['capacity_reference_rounded'], 12)

    def test_missing_level_not_zero(self):
        r = self.sample('hotel')
        self.assertIsNone(r['rows'][0]['capacity_reference_rounded'])
        self.assertEqual(r['status'], 'PARTIAL')
        self.assertEqual(r['summary_by_unit']['GUESTS_ESTIMATED']['unknown_buildings'], 1)

    def test_height_fallback_and_floor_precedence(self):
        r = self.sample('apartment', height=9, num_floors=2)
        self.assertEqual(r['rows'][0]['level'], 2)
        r = self.sample('apartment', height=9)
        self.assertEqual(r['rows'][0]['level'], 3)

    def test_rejects_invalid_level_and_mixed_total(self):
        with self.assertRaises(ValueError):
            self.sample('apartment', num_floors=True)
        p = get_config(); p['capacity_reference']['allow_mixed_unit_total'] = True
        with self.assertRaises(ValueError):
            estimate_capacity(self.selection, p)

    def test_immutability_and_duplicate(self):
        before = deepcopy(self.selection)
        estimate_capacity(self.selection)
        self.assertEqual(before, self.selection)
        self.selection['selected'].append(deepcopy(self.selection['selected'][0]))
        with self.assertRaises(ValueError):
            estimate_capacity(self.selection)


if __name__ == '__main__':
    unittest.main()
