# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from __future__ import unicode_literals

import unittest
from decimal import Decimal
from datetime import date

from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.tests.test_tryton import suite as test_suite
from trytond.pool import Pool


class CustomsTestCase(ModuleTestCase):
    'Test Customs module'
    module = 'customs'

    @with_transaction()
    def test_tariff_code_match(self):
        'Test tariff code match'
        pool = Pool()
        Tariff = pool.get('customs.tariff.code')
        Template = pool.get('product.template')
        Product_TariffCode = pool.get(
            'product-customs.tariff.code')

        # Test start <= end
        tariff1 = Tariff(code='170390')
        tariff2 = Tariff(code='17039099',
                start_month='06', start_day=20,
                end_month='08', end_day=20)
        Tariff.save([tariff1, tariff2])
        template = Template(tariff_codes=[
                Product_TariffCode(tariff_code=tariff2),
                Product_TariffCode(tariff_code=tariff1),
                ], tariff_codes_category=False)

        for pattern, result in [
                ({'date': date(2015, 1, 1)}, tariff1),
                ({'date': date(2015, 7, 1)}, tariff2),
                ({'date': date(2016, 9, 1)}, tariff1),
                ]:
            self.assertEqual(template.get_tariff_code(pattern), result)

        # Test start > end
        tariff2.start_month = '08'
        tariff2.end_month = '06'
        tariff2.save()

        for pattern, result in [
                ({'date': date(2015, 1, 1)}, tariff2),
                ({'date': date(2015, 7, 1)}, tariff1),
                ({'date': date(2016, 9, 1)}, tariff2),
                ]:
            self.assertEqual(template.get_tariff_code(pattern), result)

    @with_transaction()
    def test_get_tariff_code(self):
        'Test get_tariff_code'
        pool = Pool()
        Tariff = pool.get('customs.tariff.code')
        Template = pool.get('product.template')
        Category = pool.get('product.category')
        Product_TariffCode = pool.get(
            'product-customs.tariff.code')

        tariff1, tariff2, tariff3 = Tariff.create([
                {'code': '170390'},
                {'code': '17039099'},
                {'code': '1703909999'},
                ])

        category1 = Category(tariff_codes=[
                Product_TariffCode(tariff_code=tariff1),
                ], tariff_codes_parent=False, customs=True)
        category2 = Category(tariff_codes=[
                Product_TariffCode(tariff_code=tariff2),
                ], parent=category1, tariff_codes_parent=False, customs=True)
        template = Template(tariff_codes=[
                Product_TariffCode(tariff_code=tariff3),
                ], customs_category=category2, tariff_codes_category=False)

        self.assertEqual(template.get_tariff_code({}), tariff3)

        template.tariff_codes_category = True
        self.assertEqual(template.get_tariff_code({}), tariff2)

        category2.tariff_codes_parent = True
        self.assertEqual(template.get_tariff_code({}), tariff1)

    @with_transaction()
    def test_duty_rate_match(self):
        'Test duty rate match'
        pool = Pool()
        Tariff = pool.get('customs.tariff.code')
        Rate = pool.get('customs.duty.rate')
        Currency = pool.get('currency.currency')
        CurrencyRate = pool.get('currency.currency.rate')

        currency = Currency(name='cur', symbol='cur', code='XXX',
            rates=[CurrencyRate(rate=Decimal(1))])
        currency.save()

        tariff = Tariff(code='170390')
        tariff.save()

        rate1 = Rate(tariff_code=tariff,
            computation_type='amount',
            end_date=date(2015, 6, 30),
            amount=Decimal(10), currency=currency)
        rate2 = Rate(tariff_code=tariff,
            start_date=date(2015, 7, 1),
            end_date=date(2015, 12, 31),
            computation_type='amount',
            amount=Decimal(10), currency=currency)
        rate3 = Rate(tariff_code=tariff,
            start_date=date(2015, 12, 31),
            computation_type='amount',
            amount=Decimal(10), currency=currency)
        Rate.save([rate1, rate2, rate3])

        for pattern, result in [
                ({'date': date(2015, 1, 1)}, rate1),
                ({'date': date(2015, 8, 1)}, rate2),
                ({'date': date(2016, 9, 1)}, rate3),
                ]:
            self.assertEqual(tariff.get_duty_rate(pattern), result)

    @with_transaction()
    def test_duty_rate_compute(self):
        'Test duty rate compute'
        pool = Pool()
        Rate = pool.get('customs.duty.rate')
        Currency = pool.get('currency.currency')
        CurrencyRate = pool.get('currency.currency.rate')
        Uom = pool.get('product.uom')

        kg, g = Uom.search([('name', 'in', ['Kilogram', 'Gram'])],
            order=[('name', 'DESC')])
        currency1 = Currency(name='cur1', symbol='cur1', code='XX1',
            rates=[CurrencyRate(rate=Decimal(1))])
        currency2 = Currency(name='cur2', symbol='cur1', code='XX2',
            rates=[CurrencyRate(rate=Decimal('.5'))])
        Currency.save([currency1, currency2])

        rate = Rate(computation_type='amount',
            amount=Decimal(10), currency=currency1)
        self.assertEqual(rate.compute(currency2, 1, kg), Decimal(5))

        rate = Rate(computation_type='quantity',
            amount=Decimal(10), currency=currency1, uom=kg)
        self.assertEqual(rate.compute(currency2, 100, g), Decimal('0.5'))

    @with_transaction()
    def test_delete_category(self):
        'Test delete category'
        pool = Pool()
        Tariff = pool.get('customs.tariff.code')
        Category = pool.get('product.category')
        Product_TariffCode = pool.get(
            'product-customs.tariff.code')

        tariff = Tariff(code='170390')
        tariff.save()

        category = Category(name='Test', customs=True,
            tariff_codes=[
                Product_TariffCode(tariff_code=tariff),
                ])
        category.save()
        product_tariff_code, = category.tariff_codes

        Category.delete([category])

        self.assertEqual(
            Product_TariffCode.search([
                    ('id', '=', product_tariff_code.id),
                    ]), [])

    @with_transaction()
    def test_delete_template(self):
        'Test delete template'
        pool = Pool()
        Tariff = pool.get('customs.tariff.code')
        Template = pool.get('product.template')
        Uom = pool.get('product.uom')
        Product_TariffCode = pool.get(
            'product-customs.tariff.code')

        unit, = Uom.search([('name', '=', 'Unit')])

        tariff = Tariff(code='170390')
        tariff.save()

        template = Template(name='Test',
            default_uom=unit,
            list_price=Decimal(0),
            cost_price=Decimal(0),
            tariff_codes=[
                Product_TariffCode(tariff_code=tariff),
                ])
        template.save()
        product_tariff_code, = template.tariff_codes

        Template.delete([template])

        self.assertEqual(
            Product_TariffCode.search([
                    ('id', '=', product_tariff_code.id),
                    ]), [])


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            CustomsTestCase))
    return suite
