import unittest
import ppac
import konstatna as K

class PPACTests(unittest.TestCase):
    def residential(self, **overrides):
        args = dict(total=1000, unit='bangunan',
                    combined_coefficient=1.5, operating_days_per_week=7, swot_factor=1)
        args.update(overrides)
        return ppac.calculate_residential(**args)

    def test_allocation_conserves_fractional_total(self):
        for total in (0, 1, 101, 1.25, 1000):
            r = ppac.split_residential(total, unit='bangunan')
            self.assertAlmostEqual(r['penghuni_400m'] + r['penghuni_400_800m']
                                   + r['penghuni_gt800m'], total * 4)
            self.assertAlmostEqual(r['penghuni_400m'], total * 4 * .3)
            self.assertAlmostEqual(r['penghuni_400_800m'], total * 4 * .5)
            self.assertAlmostEqual(r['penghuni_gt800m'], total * 4 * .2)

    def test_three_bands_and_far_eligibility(self):
        r = self.residential()
        self.assertEqual((r['std_400m'], r['std_400_800m'], r['std_gt800m']), (60, 50, 10))
        self.assertEqual(r['std_residential'], 120)
        self.assertEqual(self.residential(far_eligible=False)['std_residential'], 110)
        with self.assertRaises(ValueError):
            self.residential(far_eligible=None)

    def test_units_do_not_double_multiply_people(self):
        self.assertEqual(self.residential(total=4000, unit='penghuni')['std_residential'], 120)
        with self.assertRaises(ValueError):
            self.residential(unit='kk')

    def test_excel_rounding(self):
        self.assertEqual(ppac.excel_round(2.5), 3)
        self.assertEqual(ppac.excel_round(-2.5), -3)

    def traffic(self, data):
        return ppac.calculate_traffic(data, road_type='street', operating_hours=15,
                                      balance_multiplier=.6)

    def test_missing_is_not_observed_zero(self):
        self.assertEqual(self.traffic({})['status'], 'unavailable')
        self.assertIsNone(self.traffic({})['std_traffic_raw'])
        partial = self.traffic({'weekday': {'pagi': {'motor': 0}}})
        self.assertEqual(partial['status'], 'sementara')
        self.assertEqual(partial['std_traffic_raw'], 0)
        self.assertIsNone(partial['std_by_day']['weekend'])
        complete = {d: {s: {c: 0 for c in K.CATEGORIES} for s in K.SESSIONS_NORMAL}
                    for d in K.DAY_WEIGHTS}
        self.assertEqual(self.traffic(complete)['status'], 'lengkap')

    def test_zero_fallback_is_coefficient_only(self):
        t = self.traffic({'weekday': {'pagi': {'motor': 100}},
                          'weekend': {'pagi': {'motor': 0}}})
        self.assertEqual(t['coefficients']['motor'], .25)
        self.assertEqual(t['std_by_day']['weekend'], 0)
        self.assertEqual(t['std_by_day']['weekday'], 90)
        self.assertEqual(t['std_traffic_raw'], 51)

    def test_invalid_inputs(self):
        for v in (-1, float('nan'), float('inf'), True, '100'):
            with self.subTest(v=v), self.assertRaises(ValueError):
                self.residential(total=v)
        for v in (-1, 1.5, True):
            with self.subTest(v=v), self.assertRaises(ValueError):
                self.traffic({'weekday': {'pagi': {'motor': v}}})
        with self.assertRaises(ValueError):
            self.traffic({'weekday': {'typo': {}}})

    def test_fasum_and_total(self):
        self.assertEqual(ppac.calculate_fasum(employees_students_residents=100,
                         daily_visitors=20, monthly_operating_days=30,
                         coefficient=2, distance_multiplier=.75), 6)
        r = self.residential()
        t = self.traffic({'weekday': {'pagi': {'motor': 100}},
                          'weekend': {'pagi': {'motor': 100}}})
        result = ppac.calculate_ppac(residential=r, traffic=t, fasum_std=6,
                                    traffic_cut_factor=1, parking_factor=1)
        self.assertEqual(result['std_total'], r['std_residential'] + t['std_traffic_raw'] + 6)
        self.assertEqual(result['status'], 'sementara')

if __name__ == '__main__':
    unittest.main()
