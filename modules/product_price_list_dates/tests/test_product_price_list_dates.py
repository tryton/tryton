# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest
import datetime
from decimal import Decimal

from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.tests.test_tryton import suite as test_suite

from trytond.modules.company.tests import create_company, set_company


class ProductPriceListDatesTestCase(ModuleTestCase):
    'Test Product Price List Dates module'
    module = 'product_price_list_dates'
    extras = ['sale_price_list']

    def create_price_list(self, field, date):
        pool = Pool()
        PriceList = pool.get('product.price_list')

        company = create_company()
        with set_company(company):
            price_list, = PriceList.create([{
                        'name': "Price List",
                        'lines': [('create', [{
                                        field: date,
                                        'formula': 'unit_price * 0.9',
                                        }, {
                                        'formula': 'unit_price',
                                        }])],
                        }])
        return price_list

    @with_transaction()
    def test_price_list_start_date(self):
        "Test price list with start date"
        pool = Pool()
        Date = pool.get('ir.date')

        today = Date.today()
        tomorrow = today + datetime.timedelta(days=1)

        price_list = self.create_price_list('start_date', tomorrow)

        self.assertEqual(
            price_list.compute(
                None, None, Decimal(10), 1, None, pattern={'date': today}),
            Decimal(10))
        self.assertEqual(
            price_list.compute(
                None, None, Decimal(10), 1, None, pattern={'date': tomorrow}),
            Decimal(9))

    @with_transaction()
    def test_price_list_end_date(self):
        "Test price list with end date"
        pool = Pool()
        Date = pool.get('ir.date')

        today = Date.today()
        yesterday = today - datetime.timedelta(days=1)

        price_list = self.create_price_list('end_date', yesterday)

        self.assertEqual(
            price_list.compute(
                None, None, Decimal(10), 1, None, pattern={'date': today}),
            Decimal(10))
        self.assertEqual(
            price_list.compute(
                None, None, Decimal(10), 1, None, pattern={'date': yesterday}),
            Decimal(9))


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            ProductPriceListDatesTestCase))
    return suite
