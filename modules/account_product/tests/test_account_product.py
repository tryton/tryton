# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
from decimal import Decimal

import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.pool import Pool
from trytond.exceptions import UserError

from trytond.modules.company.tests import create_company, set_company
from trytond.modules.account.tests import create_chart


class AccountProductTestCase(ModuleTestCase):
    'Test AccountProduct module'
    module = 'account_product'

    @with_transaction()
    def test_account_used(self):
        'Test account used'
        pool = Pool()
        ProductTemplate = pool.get('product.template')
        ProductCategory = pool.get('product.category')
        Uom = pool.get('product.uom')
        Account = pool.get('account.account')

        company = create_company()
        with set_company(company):
            create_chart(company)

            unit, = Uom.search([
                    ('name', '=', 'Unit'),
                    ])
            account_expense, = Account.search([
                    ('kind', '=', 'expense'),
                    ])

            # raise when empty
            template = ProductTemplate(
                name='test account used',
                list_price=Decimal(10),
                cost_price=Decimal(3),
                default_uom=unit.id,
                )
            template.save()

            self.assertIsNone(template.account_expense)

            with self.assertRaises(UserError):
                template.account_expense_used

            # with account
            template = ProductTemplate(
                name='test account used',
                list_price=Decimal(10),
                cost_price=Decimal(3),
                default_uom=unit.id,
                account_expense=account_expense.id,
                )
            template.save()

            self.assertEqual(template.account_expense, account_expense)
            self.assertEqual(template.account_expense_used, account_expense)

            # with account on category
            category = ProductCategory(name='test account used',
                account_expense=account_expense, accounting=True)
            category.save()
            template.account_expense = None
            template.accounts_category = True
            template.account_category = category
            template.save()

            self.assertIsNone(template.account_expense)
            self.assertEqual(template.account_expense_used, account_expense)

            # with account on grant category
            parent_category = ProductCategory(name='parent account used',
                account_expense=account_expense, accounting=True)
            parent_category.save()
            category.account_expense = None
            category.account_parent = True
            category.parent = parent_category
            category.save()

            self.assertIsNone(category.account_expense)
            self.assertEqual(template.account_expense_used, account_expense)
            self.assertEqual(category.account_expense_used, account_expense)

            # raise only at direct usage
            templates = ProductTemplate.create([{
                        'name': 'test with account',
                        'list_price': Decimal(10),
                        'cost_price': Decimal(3),
                        'default_uom': unit.id,
                        'account_expense': account_expense.id,
                        }, {
                        'name': 'test without account',
                        'list_price': Decimal(10),
                        'cost_price': Decimal(3),
                        'default_uom': unit.id,
                        'account_expense': None,
                        }])

            self.assertEqual(templates[0].account_expense_used.id,
                account_expense.id)

            with self.assertRaises(UserError):
                templates[1].account_expense_used


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        AccountProductTestCase))
    return suite
