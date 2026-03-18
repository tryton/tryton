# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from unittest.mock import Mock

from trytond.modules.account.tests import create_chart
from trytond.modules.company.tests import (
    CompanyTestMixin, create_company, set_company)
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class AccountTaxRuleCountryTestCase(CompanyTestMixin, ModuleTestCase):
    'Test Account Tax Rule Country module'
    module = 'account_tax_rule_country'
    extras = ['account_invoice', 'sale', 'purchase', 'stock']

    @with_transaction()
    def test_account_chart(self):
        'Test creation and update of minimal chart of accounts'
        pool = Pool()
        Account = pool.get('account.account')
        UpdateChart = pool.get('account.update_chart', type='wizard')

        company = create_company()
        with set_company(company):
            create_chart(company, tax=True)
            root, = Account.search([('parent', '=', None)])

            session_id, _, _ = UpdateChart.create()
            update_chart = UpdateChart(session_id)
            update_chart.start.account = root
            update_chart.transition_update()

    @classmethod
    def _create_countries(cls):
        pool = Pool()
        Country = pool.get('country.country')
        Subdivision = pool.get('country.subdivision')

        country1 = Country(name="Country 1")
        country1.save()
        subdivision1 = Subdivision(
            country=country1, name="Subdivision 1", code="SUB1",
            type='province')
        subdivision1.save()
        subdivision11 = Subdivision(
            country=country1, parent=subdivision1,
            name="Sub-Subdivision 1", code="SUBSUB1", type='province')
        subdivision11.save()
        country2 = Country(name="Country 2")
        country2.save()
        subdivision2 = Subdivision(
            country=country2, name="Subdivision 2", code="SUB2",
            type='province')
        subdivision2.save()

        return [country1, country2]

    def _get_taxes(cls):
        pool = Pool()
        Tax = pool.get('account.tax')
        tax, = Tax.search([])
        target_tax, = Tax.copy([tax])
        return [tax, target_tax]

    def _create_rule(cls, lines):
        pool = Pool()
        TaxRule = pool.get('account.tax.rule')
        return TaxRule.create([{
                    'name': 'Test',
                    'kind': 'both',
                    'lines': [('create', lines)],
                    }])[0]

    @with_transaction()
    def test_tax_rule(self):
        "Test tax rule"
        country1, country2 = self._create_countries()[:2]
        subdivision1 = country1.subdivisions[0]
        subdivision2 = country2.subdivisions[0]
        company = create_company()
        with set_company(company):
            create_chart(company, tax=True)
            tax, target_tax = self._get_taxes()[:2]
            tax_rule = self._create_rule([{
                        'from_country': country1.id,
                        'from_subdivision': subdivision1.id,
                        'to_country': country2.id,
                        'to_subdivision': subdivision2.id,
                        'origin_tax': tax.id,
                        'tax': target_tax.id,
                        }])
            pattern = {
                'from_country': country1.id,
                'from_subdivision': subdivision1.id,
                'to_country': country2.id,
                'to_subdivision': subdivision2.id,
                }

            self.assertListEqual(tax_rule.apply(tax, pattern), [target_tax.id])

    @with_transaction()
    def test_tax_rule_children(self):
        "Test tax rule with children subdivision"
        country = self._create_countries()[0]
        parent_subdivision = [
            s for s in country.subdivisions if not s.parent][0]
        subdivision = [
            s for s in country.subdivisions
            if s.parent == parent_subdivision][0]
        company = create_company()
        with set_company(company):
            create_chart(company, tax=True)
            tax, target_tax = self._get_taxes()[:2]
            tax_rule = self._create_rule([{
                        'to_country': country.id,
                        'to_subdivision': parent_subdivision.id,
                        'origin_tax': tax.id,
                        'tax': target_tax.id,
                        }])
            pattern = {
                'to_country': country.id,
                'to_subdivision': subdivision.id,
                }

            self.assertListEqual(tax_rule.apply(tax, pattern), [target_tax.id])

    @with_transaction()
    def test_tax_rule_no_subdivision(self):
        "Test tax rule without subdivision"
        country = self._create_countries()[0]
        subdivision = country.subdivisions[0]
        company = create_company()
        with set_company(company):
            create_chart(company, tax=True)
            tax, target_tax = self._get_taxes()[:2]
            tax_rule = self._create_rule([{
                        'to_country': country.id,
                        'origin_tax': tax.id,
                        'tax': target_tax.id,
                        }])
            pattern = {
                'to_country': country.id,
                'to_subdivision': subdivision.id,
                }

            self.assertListEqual(tax_rule.apply(tax, pattern), [target_tax.id])

    @with_transaction()
    def test_tax_rule_no_subdivision_pattern(self):
        "Test tax rule without subdivision in pattern"
        country = self._create_countries()[0]
        subdivision = country.subdivisions[0]
        company = create_company()
        with set_company(company):
            create_chart(company, tax=True)
            tax, target_tax = self._get_taxes()[:2]
            tax_rule = self._create_rule([{
                        'to_country': country.id,
                        'to_subdivision': subdivision.id,
                        'origin_tax': tax.id,
                        'tax': target_tax.id,
                        }])
            pattern = {
                'to_country': country.id,
                }

            self.assertListEqual(tax_rule.apply(tax, pattern), [tax.id])

    @with_transaction()
    def test_check_tax_rule_pattern_no_origin(self):
        "Check tax rule pattern without origin"
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        invoice_line = InvoiceLine(origin=None, invoice=None)

        pattern = invoice_line._get_tax_rule_pattern()

        self.assertEqual(pattern, pattern | {
                'from_country': None,
                'from_subdivision': None,
                'to_country': None,
                'to_subdivision': None,
                })

    @with_transaction()
    def test_check_tax_rule_pattern_origin_sale_line(self):
        "Check tax rule pattern with sale line origin"
        pool = Pool()
        Address = pool.get('party.address')
        InvoiceLine = pool.get('account.invoice.line')
        Location = pool.get('stock.location')
        Sale = pool.get('sale.sale')
        SaleLine = pool.get('sale.line')

        country1, country2 = self._create_countries()
        subdivision1 = country1.subdivisions[0]
        subdivision2 = country2.subdivisions[0]
        warehouse = Mock(spec=Location, address=Mock(
                spec=Address, country=country1, subdivision=subdivision1))
        invoice_line = InvoiceLine(origin=None, invoice=None)
        invoice_line.origin = Mock(
            spec=SaleLine, id=1, warehouse=warehouse,
            sale=Mock(spec=Sale, shipment_address=Mock(
                    spec=Address, country=country2, subdivision=subdivision2)))

        for level in range(3):
            with self.subTest(level=level):
                pattern = invoice_line._get_tax_rule_pattern()

                self.assertEqual(pattern, pattern | {
                        'from_country': country1.id,
                        'from_subdivision': subdivision1.id,
                        'to_country': country2.id,
                        'to_subdivision': subdivision2.id,
                        })

                invoice_line.origin = Mock(
                    spec=InvoiceLine, id=1, origin=invoice_line.origin)

    @with_transaction()
    def test_check_tax_rule_pattern_origin_purchase_line(self):
        "Check tax rule pattern with purchase line origin"
        pool = Pool()
        Address = pool.get('party.address')
        InvoiceLine = pool.get('account.invoice.line')
        Location = pool.get('stock.location')
        Purchase = pool.get('purchase.purchase')
        PurchaseLine = pool.get('purchase.line')

        country1, country2 = self._create_countries()
        subdivision1 = country1.subdivisions[0]
        subdivision2 = country2.subdivisions[0]
        warehouse = Mock(spec=Location, address=Mock(
                spec=Address, country=country1, subdivision=subdivision1))
        invoice_line = InvoiceLine(origin=None, invoice=None)
        invoice_line.origin = Mock(
            spec=PurchaseLine, id=1, warehouse=warehouse,
            purchase=Mock(spec=Purchase, invoice_address=Mock(
                    spec=Address, country=country2, subdivision=subdivision2)))
        for level in range(3):
            with self.subTest(level=level):
                pattern = invoice_line._get_tax_rule_pattern()

                self.assertEqual(pattern, pattern | {
                        'from_country': country2.id,
                        'from_subdivision': subdivision2.id,
                        'to_country': country1.id,
                        'to_subdivision': subdivision1.id,
                        })
                invoice_line.origin = Mock(
                    spec=InvoiceLine, id=1, origin=invoice_line.origin)

    @with_transaction()
    def test_check_tax_rule_pattern_origin_stock_move_from_location(self):
        "Check tax rule pattern with stock move from location origin"
        pool = Pool()
        Address = pool.get('party.address')
        InvoiceLine = pool.get('account.invoice.line')
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')

        country, _ = self._create_countries()
        subdivision = country.subdivisions[0]
        warehouse = Mock(spec=Location, address=Mock(
                spec=Address, country=country, subdivision=subdivision))
        invoice_line = InvoiceLine(origin=None, invoice=None)
        invoice_line.origin = Mock(
            spec=Move, id=1,
            from_location=Mock(spec=Location, warehouse=warehouse))
        for level in range(3):
            with self.subTest(level=level):
                pattern = invoice_line._get_tax_rule_pattern()

                self.assertEqual(pattern, pattern | {
                        'from_country': country.id,
                        'from_subdivision': subdivision.id,
                        })

                invoice_line.origin = Mock(
                    spec=InvoiceLine, id=1, origin=invoice_line.origin)

    @with_transaction()
    def test_check_tax_rule_pattern_origin_shipment_out_return(self):
        "Check tax rule pattern with shipment out return origin"
        pool = Pool()
        Address = pool.get('party.address')
        InvoiceLine = pool.get('account.invoice.line')
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')
        ShipmentOutReturn = pool.get('stock.shipment.out.return')

        country, _ = self._create_countries()
        subdivision = country.subdivisions[0]
        invoice_line = InvoiceLine(origin=None, invoice=None)
        invoice_line.origin = Mock(
            spec=Move, id=1,
            from_location=Mock(spec=Location, warehouse=None),
            origin=Mock(spec=ShipmentOutReturn, delivery_address=Mock(
                    spec=Address, country=country, subdivision=subdivision)))

        for level in range(3):
            with self.subTest(level=level):
                pattern = invoice_line._get_tax_rule_pattern()

                self.assertEqual(pattern, pattern | {
                        'from_country': country.id,
                        'from_subdivision': subdivision.id,
                        })

                invoice_line.origin = Mock(
                    spec=InvoiceLine, id=1, origin=invoice_line.origin)

    @with_transaction()
    def test_check_tax_rule_pattern_origin_stock_move_to_location(self):
        "Check tax rule pattern with stock move to location origin"
        pool = Pool()
        Address = pool.get('party.address')
        InvoiceLine = pool.get('account.invoice.line')
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')

        country, _ = self._create_countries()
        subdivision = country.subdivisions[0]
        warehouse = Mock(spec=Location, address=Mock(
                spec=Address, country=country, subdivision=subdivision))
        invoice_line = InvoiceLine(origin=None, invoice=None)
        invoice_line.origin = Mock(
            spec=Move, id=1,
            to_location=Mock(spec=Location, warehouse=warehouse))

        for level in range(3):
            with self.subTest(level=level):
                pattern = invoice_line._get_tax_rule_pattern()

                self.assertEqual(pattern, pattern | {
                        'to_country': country.id,
                        'to_subdivision': subdivision.id,
                        })

                invoice_line.origin = Mock(
                    spec=InvoiceLine, id=1, origin=invoice_line.origin)

    @with_transaction()
    def test_check_tax_rule_pattern_origin_shipment_out(self):
        "Check tax rule pattern with shipment out origin"
        pool = Pool()
        Address = pool.get('party.address')
        InvoiceLine = pool.get('account.invoice.line')
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')
        ShipmentOut = pool.get('stock.shipment.out')

        country, _ = self._create_countries()
        subdivision = country.subdivisions[0]
        invoice_line = InvoiceLine(origin=None, invoice=None)
        invoice_line.origin = Mock(
            spec=Move, id=1,
            to_location=Mock(spec=Location, warehouse=None),
            origin=Mock(spec=ShipmentOut, delivery_address=Mock(
                    spec=Address, country=country, subdivision=subdivision)))

        for level in range(3):
            with self.subTest(level=level):
                pattern = invoice_line._get_tax_rule_pattern()

                self.assertEqual(pattern, pattern | {
                        'to_country': country.id,
                        'to_subdivision': subdivision.id,
                        })

                invoice_line.origin = Mock(
                    spec=InvoiceLine, id=1, origin=invoice_line.origin)


del ModuleTestCase
