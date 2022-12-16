# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import doctest
import datetime

import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.tests.test_tryton import doctest_teardown
from trytond.tests.test_tryton import doctest_checker
from trytond.pool import Pool


class ProductionTestCase(ModuleTestCase):
    'Test Production module'
    module = 'production'

    @with_transaction()
    def test_on_change_with_planned_start_date(self):
        "Test on_change_with_planned_start_date"
        pool = Pool()
        Production = pool.get('production')
        Product = pool.get('product.product')
        LeadTime = pool.get('production.lead_time')

        date = datetime.date(2016, 11, 26)
        product = Product()
        product.lead_times = []
        production = Production()
        production.planned_date = date
        production.product = product

        self.assertEqual(production.on_change_with_planned_start_date(), date)

        lead_time = LeadTime(bom=None, lead_time=None)
        product.lead_times = [lead_time]
        self.assertEqual(production.on_change_with_planned_start_date(), date)

        lead_time.lead_time = datetime.timedelta(1)
        self.assertEqual(
            production.on_change_with_planned_start_date(),
            datetime.date(2016, 11, 25))


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            ProductionTestCase))
    suite.addTests(doctest.DocFileSuite('scenario_production.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
