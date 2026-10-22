import unittest

from location_intelligent_overture_probe import normalize

try:
    from osgeo import ogr
    GEO = True
except ImportError:
    GEO = False


@unittest.skipUnless(GEO, 'Use system Python/GDAL')
class OvertureNormalizationTests(unittest.TestCase):
    def setUp(self):
        geom = ogr.CreateGeometryFromWkt('POLYGON ((106 -6,106.001 -6,106.001 -6.001,106 -6.001,106 -6))')
        self.raw = {'release': '2026-10-21.0', 'schema_version': '2.0.0', 'rows': [
            {'id': 'actual-style-stable-id', 'class': None, 'subtype': None, 'height': None,
             'num_floors': None, 'version': 1, 'sources': [], 'geometry_wkb_hex': bytes(geom.ExportToWkb()).hex()}]}

    def test_nulls_preserved_not_fabricated_as_residential(self):
        r = normalize(self.raw)
        p = r['features'][0]['properties']
        self.assertIsNone(p['class'])
        self.assertIsNone(p['subclass'])
        self.assertIsNone(p['height'])
        self.assertEqual(r['features'][0]['geometry']['type'], 'Polygon')

    def test_subtype_mapping_and_source_lineage(self):
        self.raw['rows'][0]['subtype'] = 'residential'
        self.raw['rows'][0]['sources'] = [{'dataset': 'fixture', 'license': 'fixture'}]
        r = normalize(self.raw)['features'][0]['properties']
        self.assertEqual(r['subclass'], 'residential')
        self.assertEqual(r['sources'], self.raw['rows'][0]['sources'])

    def test_wrong_release_rejected(self):
        self.raw['release'] = '2026-08-19.0'
        with self.assertRaises(ValueError):
            normalize(self.raw)

    def test_missing_column_rejected(self):
        del self.raw['rows'][0]['class']
        with self.assertRaises(ValueError):
            normalize(self.raw)


if __name__ == '__main__':
    unittest.main()
