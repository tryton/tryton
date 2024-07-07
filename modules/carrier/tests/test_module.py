# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from decimal import Decimal

from trytond.modules.company.tests import create_company, set_company
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


def create_carrier(list_price=None, cost_price=None):
    pool = Pool()
    Carrier = pool.get('carrier')
    Party = pool.get('party.party')
    Product = pool.get('product.product')
    ProductTemplate = pool.get('product.template')
    UoM = pool.get('product.uom')

    unit, = UoM.search([('name', '=', "Unit")])
    party = Party(name="Carrier")
    party.save()
    product_template = ProductTemplate(
        name="Service",
        type='service',
        default_uom=unit)
    if list_price is not None:
        product_template.list_price = list_price
    product_template.save()
    product = Product(template=product_template)
    if cost_price is not None:
        product.cost_price = cost_price
    product.save()
    carrier = Carrier(party=party, carrier_product=product)
    carrier.save()
    return carrier


class CarrierTestCase(ModuleTestCase):
    'Test Carrier module'
    module = 'carrier'

    @with_transaction()
    def test_carrier_rec_name(self):
        "Test carrier record name"
        carrier = create_carrier()
        self.assertEqual(carrier.rec_name, "Carrier - Service")

    @with_transaction()
    def test_carrier_search_rec_name(self):
        "Test search carrier by record name"
        pool = Pool()
        Carrier = pool.get('carrier')
        carrier = create_carrier()

        for domain, result in [
                ([('rec_name', 'ilike', "Carrier%")], [carrier]),
                ([('rec_name', 'ilike', "%Service")], [carrier]),
                ([('rec_name', 'not ilike', "Carrier%")], []),
                ([('rec_name', 'not ilike', "%Service")], []),
                ]:
            with self.subTest(domain=domain):
                self.assertEqual(Carrier.search(domain), result)

    @with_transaction()
    def test_carrier_sale_price(self):
        "Test carrier sale price"
        company = create_company()
        with set_company(company):
            carrier = create_carrier(list_price=Decimal('42.0000'))
            self.assertEqual(
                carrier.get_sale_price(),
                (Decimal('42.0000'), company.currency.id))

    @with_transaction()
    def test_carrier_sale_price_without_list_price(self):
        "Test carrier sale price without list price"
        company = create_company()
        with set_company(company):
            carrier = create_carrier()
            self.assertEqual(carrier.get_sale_price(), (None, None))

    @with_transaction()
    def test_carrier_sale_price_without_company(self):
        "Test carrier sale price without company"
        carrier = create_carrier()
        self.assertEqual(carrier.get_sale_price(), (None, None))

    @with_transaction()
    def test_carrier_purchase_price(self):
        "Test carrier purchase price"
        company = create_company()
        with set_company(company):
            carrier = create_carrier(cost_price=Decimal('42.0000'))
            self.assertEqual(
                carrier.get_purchase_price(),
                (Decimal('42.0000'), company.currency.id))

    @with_transaction()
    def test_carrier_purchase_price_without_cost_price(self):
        "Test carrier sale price without cost price"
        carrier = create_carrier()
        company = create_company()
        with set_company(company):
            self.assertEqual(carrier.get_purchase_price(), (None, None))

    @with_transaction()
    def test_carrier_purchase_price_without_company(self):
        "Test carrier purchase price without company"
        carrier = create_carrier()
        self.assertEqual(carrier.get_purchase_price(), (None, None))

    @with_transaction()
    def test_carrier_selection(self):
        "Test carrier selection"
        pool = Pool()
        Selection = pool.get('carrier.selection')
        Country = pool.get('country.country')

        carrier1 = create_carrier()
        carrier2 = create_carrier()
        country1 = Country(name="Country 1")
        country1.save()
        country2 = Country(name="Country 2")
        country2.save()

        selection1 = Selection(carrier=carrier1, to_country=country1)
        selection1.save()
        selection2 = Selection(carrier=carrier2)
        selection2.save()

        for pattern, carriers in [
                ({'to_country': country1.id}, [carrier1, carrier2]),
                ({}, [carrier1, carrier2]),
                ({'to_country': country2.id}, [carrier2]),
                ]:
            with self.subTest(pattern=pattern):
                self.assertEqual(Selection.get_carriers(pattern), carriers)

    @with_transaction()
    def test_carrier_selection_wihout_selection(self):
        "Test carrier selection without selection"
        pool = Pool()
        Selection = pool.get('carrier.selection')

        carrier1 = create_carrier()
        carrier2 = create_carrier()
        carrier2.active = False
        carrier2.save()

        self.assertEqual(Selection.get_carriers({}), [carrier1, carrier2])


del ModuleTestCase
