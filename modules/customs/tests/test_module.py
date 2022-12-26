# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from datetime import date
from decimal import Decimal

from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class CustomsTestCase(ModuleTestCase):
    'Test Customs module'
    module = 'customs'

    @with_transaction()
    def test_tariff_code_match_date(self):
        "Test tariff code match date"
        pool = Pool()
        Tariff = pool.get('customs.tariff.code')
        Template = pool.get('product.template')
        Product_TariffCode = pool.get(
            'product-customs.tariff.code')
        Month = pool.get('ir.calendar.month')

        june, = Month.search([('index', '=', 6)])
        august, = Month.search([('index', '=', 8)])

        # Test start <= end
        tariff1 = Tariff(code='170390')
        tariff2 = Tariff(code='17039099',
                start_month=june, start_day=20,
                end_month=august, end_day=20)
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
        tariff2.start_month = august
        tariff2.end_month = june
        tariff2.save()

        for pattern, result in [
                ({'date': date(2015, 1, 1)}, tariff2),
                ({'date': date(2015, 7, 1)}, tariff1),
                ({'date': date(2016, 9, 1)}, tariff2),
                ]:
            self.assertEqual(template.get_tariff_code(pattern), result)

    @with_transaction()
    def test_tariff_code_match_country(self):
        "Test tariff code match country"
        pool = Pool()
        Tariff = pool.get('customs.tariff.code')
        Country = pool.get('country.country')

        country1 = Country(name="Country 1")
        country1.save()
        country2 = Country(name="Country 2")
        country2.save()
        tariff1 = Tariff(code='170390')
        tariff1.save()
        tariff2 = Tariff(code='17039099', country=country1)
        tariff2.save()

        self.assertTrue(tariff1.match({}))
        self.assertTrue(tariff1.match({'country': None}))
        self.assertTrue(tariff1.match({'country': country1.id}))
        self.assertTrue(tariff2.match({}))
        self.assertTrue(tariff2.match({'country': None}))
        self.assertTrue(tariff2.match({'country': country1.id}))
        self.assertFalse(tariff2.match({'country': country2.id}))

    @with_transaction()
    def test_tariff_code_match_country_organization(self):
        "Test Tariff code match country with organization"
        pool = Pool()
        Tariff = pool.get('customs.tariff.code')
        Country = pool.get('country.country')
        Organization = pool.get('country.organization')

        country1 = Country(name="Country 1")
        country1.save()
        country2 = Country(name="Country 2")
        country2.save()
        organization = Organization(
            name="Organization", members=[{'country': country1.id}])
        organization.save()
        tariff1 = Tariff(code='170390')
        tariff1.save()
        tariff2 = Tariff(code='17039099', organization=organization)
        tariff2.save()

        self.assertTrue(tariff1.match({}))
        self.assertTrue(tariff1.match({'country': None}))
        self.assertTrue(tariff1.match({'country': country1.id}))
        self.assertTrue(tariff2.match({}))
        self.assertTrue(tariff2.match({'country': None}))
        self.assertTrue(tariff2.match({'country': country1.id}))
        self.assertFalse(tariff2.match({'country': country2.id}))

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


del ModuleTestCase
