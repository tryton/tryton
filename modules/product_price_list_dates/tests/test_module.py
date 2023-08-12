# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime
from decimal import Decimal

from trytond.modules.company.tests import (
    CompanyTestMixin, create_company, set_company)
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.transaction import Transaction


class ProductPriceListDatesTestCase(CompanyTestMixin, ModuleTestCase):
    'Test Product Price List Dates module'
    module = 'product_price_list_dates'
    extras = [
        'product_price_list_cache', 'sale_price_list', 'purchase_price_list']

    def create_price_list(self, field, date):
        pool = Pool()
        PriceList = pool.get('product.price_list')

        price_list, = PriceList.create([{
                    'name': "Price List",
                    'price': 'list_price',
                    'lines': [('create', [{
                                    field: date,
                                    'formula': 'unit_price * 0.9',
                                    }, {
                                    'formula': 'unit_price',
                                    }])],
                    }])
        return price_list

    def create_product(self, list_price=Decimal(10)):
        pool = Pool()
        Product = pool.get('product.product')
        Template = pool.get('product.template')
        Uom = pool.get('product.uom')

        unit, = Uom.search([('name', '=', "Unit")])
        template = Template(
            name="Template", list_price=list_price, default_uom=unit)
        template.save()
        product = Product(template=template)
        product.save()
        return product

    @with_transaction()
    def test_price_list_start_date(self):
        "Test price list with start date"
        pool = Pool()
        Date = pool.get('ir.date')

        today = Date.today()
        tomorrow = today + datetime.timedelta(days=1)

        company = create_company()
        with set_company(company):
            product = self.create_product()
            uom = product.default_uom
            price_list = self.create_price_list('start_date', tomorrow)

            self.assertEqual(
                price_list.compute(
                    product, 1, uom, pattern={'date': today}),
                Decimal(10))
            self.assertEqual(
                price_list.compute(
                    product, 1, uom, pattern={'date': tomorrow}),
                Decimal(9))

    @with_transaction()
    def test_price_list_end_date(self):
        "Test price list with end date"
        pool = Pool()
        Date = pool.get('ir.date')

        today = Date.today()
        yesterday = today - datetime.timedelta(days=1)

        company = create_company()
        with set_company(company):
            product = self.create_product()
            uom = product.default_uom
            price_list = self.create_price_list('end_date', yesterday)

            self.assertEqual(
                price_list.compute(
                    product, 1, uom, pattern={'date': today}),
                Decimal(10))
            self.assertEqual(
                price_list.compute(
                    product, 1, uom, pattern={'date': yesterday}),
                Decimal(9))

    @with_transaction()
    def test_price_list_with_context_date(self):
        "Test price list with context date"
        pool = Pool()
        Date = pool.get('ir.date')

        today = Date.today()
        tomorrow = today + datetime.timedelta(days=1)

        company = create_company()
        with set_company(company):
            product = self.create_product()
            uom = product.default_uom
            price_list = self.create_price_list('start_date', tomorrow)

            with Transaction().set_context(date=today):
                self.assertEqual(
                    price_list.compute(product, 1, uom),
                    Decimal(10))
            with Transaction().set_context(date=tomorrow):
                self.assertEqual(
                    price_list.compute(product, 1, uom),
                    Decimal(9))

    @with_transaction()
    def test_price_list_cache(self):
        "Test price list cache"
        pool = Pool()
        Cache = pool.get('product.price_list.cache')
        Date = pool.get('ir.date')

        today = Date.today()
        tomorrow = today + datetime.timedelta(days=1)

        company = create_company()
        with set_company(company):
            product = self.create_product()
            uom = product.default_uom
            price_list = self.create_price_list('start_date', tomorrow)

            price_list.fill_cache()

            caches = Cache.search([])
            self.assertEqual(len(caches), 2)

            for date, result in [
                    (today, Decimal(10)),
                    (tomorrow, Decimal(9)),
                    ]:
                with self.subTest(date=date):
                    with Transaction().set_context(date=date):
                        cache = Cache.get(price_list, product)
                        self.assertEqual(cache.get_unit_price(1, uom), result)


del ModuleTestCase
