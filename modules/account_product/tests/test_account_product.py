# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import doctest
from decimal import Decimal

import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction
from trytond.exceptions import UserError


class AccountProductTestCase(ModuleTestCase):
    'Test AccountProduct module'
    module = 'account_product'

    def test_account_used(self):
        'Test account used'
        ProductTemplate = POOL.get('product.template')
        ProductCategory = POOL.get('product.category')
        Uom = POOL.get('product.uom')
        Account = POOL.get('account.account')

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            unit, = Uom.search([
                    ('name', '=', 'Unit'),
                    ])
            unit_id = unit.id

            template = ProductTemplate(
                name='test account used',
                list_price=Decimal(10),
                cost_price=Decimal(3),
                default_uom=unit_id,
                )
            template.save()

            self.assertIsNone(template.account_expense)

            with self.assertRaises(UserError):
                template.account_expense_used

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            account_expense, = Account.search([
                    ('kind', '=', 'expense'),
                    ])
            account_expense_id = account_expense.id

            template = ProductTemplate(
                name='test account used',
                list_price=Decimal(10),
                cost_price=Decimal(3),
                default_uom=unit_id,
                account_expense=account_expense_id,
                )
            template.save()

            self.assertEqual(template.account_expense, account_expense)
            self.assertEqual(template.account_expense_used, account_expense)

            category = ProductCategory(name='test account used',
                account_expense=account_expense)
            category.save()
            template.account_expense = None
            template.account_category = True
            template.category = category
            template.save()

            self.assertIsNone(template.account_expense)
            self.assertEqual(template.account_expense_used, account_expense)

            parent_category = ProductCategory(name='parent account used',
                account_expense=account_expense)
            parent_category.save()
            category.account_expense = None
            category.account_parent = True
            category.parent = parent_category
            category.save()

            self.assertIsNone(category.account_expense)
            self.assertEqual(template.account_expense_used, account_expense)
            self.assertEqual(category.account_expense_used, account_expense)

        with Transaction().start(DB_NAME, USER, context=CONTEXT):

            templates = ProductTemplate.create([{
                        'name': 'test with account',
                        'list_price': Decimal(10),
                        'cost_price': Decimal(3),
                        'default_uom': unit_id,
                        'account_expense': account_expense_id,
                        }, {
                        'name': 'test without account',
                        'list_price': Decimal(10),
                        'cost_price': Decimal(3),
                        'default_uom': unit_id,
                        'account_expense': None,
                        }])

            self.assertEqual(templates[0].account_expense_used.id,
                account_expense_id)

            with self.assertRaises(UserError):
                templates[1].account_expense_used


def suite():
    suite = trytond.tests.test_tryton.suite()
    from trytond.modules.account.tests import test_account
    for test in test_account.suite():
        if test not in suite and not isinstance(test, doctest.DocTestCase):
            suite.addTest(test)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        AccountProductTestCase))
    return suite
