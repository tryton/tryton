# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

from trytond.pool import Pool
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction

from trytond.modules.company.tests import create_company, set_company
from trytond.modules.account.tests import create_chart


class AccountTaxRuleCountryTestCase(ModuleTestCase):
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


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        AccountTaxRuleCountryTestCase))
    return suite
