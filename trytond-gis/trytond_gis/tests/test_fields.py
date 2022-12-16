# This file is part of trytond_gis.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
from sql import Null

from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction


class TestGeographicFields(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_create_save(self):
        "Testing create/write with GIS types"
        pool = Pool()

        GISPoint = pool.get('test.gis.point')
        point_a = {
            'meta': {'srid': 4326},
            'type': 'Point',
            'coordinates': [1.0, 2.0],
            }
        point, = GISPoint.create([{
                    'point': point_a,
                    }])
        self.assertDictContainsSubset(point_a, point.point)

        point_b = {
            'meta': {'srid': 4326},
            'type': 'Point',
            'coordinates': [2.0, 1.0],
            }
        point.point = point_b
        point.save()

        reload_point = GISPoint(point.id)
        self.assertDictContainsSubset(point_b, reload_point.point)

        point.point = Null
        point.save()

        reload_point = GISPoint(point.id)
        self.assertIsNone(reload_point.point)

    @with_transaction()
    def test_search(self):
        "Testing search with GIS types"
        pool = Pool()

        GISPoint = pool.get('test.gis.point')
        point_a = {
            'meta': {'srid': 4326},
            'type': 'Point',
            'coordinates': [1.0, 2.0],
            }
        point_b = {
            'meta': {'srid': 4326},
            'type': 'Point',
            'coordinates': [2.0, 1.0],
            }
        GISPoint.create([{
                    'point': point_a,
                    }, {
                    'point': point_a,
                    }, {
                    'point': point_b,
                    }, {
                    }])

        points = GISPoint.search([
                ('point', '=', point_a),
                ])
        self.assertEqual(len(points), 2)
        for point in points:
            self.assertDictContainsSubset(point_a, point.point)

        points = GISPoint.search([
                ('point', '!=', point_a),
                ])
        # For some reasons NULL are not taken into account
        self.assertEqual(len(points), 1)
        self.assertNotEqual(points[0].point, point_a)

        points = GISPoint.search([
                ('point', '=', Null),
                ])
        self.assertEqual(len(points), 1)
        self.assertIsNone(points[0].point)

        points = GISPoint.search([
                ('point', '!=', Null),
                ])
        self.assertEqual(len(points), 3)
        for point in points:
            self.assertIsNotNone(point.point)


def suite():
    suite_ = unittest.TestSuite()
    suite_.addTests(unittest.TestLoader().loadTestsFromTestCase(
            TestGeographicFields))
    return suite_
