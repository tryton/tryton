# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import doctest
from decimal import Decimal
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction
from trytond.exceptions import UserWarning


class SaleCreditLimitTestCase(ModuleTestCase):
    'Test SaleCreditLimit module'
    module = 'sale_credit_limit'

    def setUp(self):
        super(SaleCreditLimitTestCase, self).setUp()
        self.account = POOL.get('account.account')
        self.move = POOL.get('account.move')
        self.period = POOL.get('account.period')
        self.journal = POOL.get('account.journal')
        self.party = POOL.get('party.party')
        self.sale = POOL.get('sale.sale')
        self.sale_line = POOL.get('sale.line')
        self.company = POOL.get('company.company')
        self.payment_term = POOL.get('account.invoice.payment_term')
        self.property = POOL.get('ir.property')
        self.model_field = POOL.get('ir.model.field')

    def test0010check_credit_limit(self):
        'Test check_credit_limit'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            receivable, = self.account.search([
                    ('kind', '=', 'receivable'),
                    ])
            revenue, = self.account.search([
                    ('kind', '=', 'revenue'),
                    ])
            journal, = self.journal.search([], limit=1)
            period, = self.period.search([], limit=1)
            party, = self.party.create([{
                        'name': 'Party',
                        'addresses': [
                            ('create', [{}]),
                            ],
                        'credit_limit_amount': Decimal('100'),
                        }])
            self.move.create([{
                        'journal': journal.id,
                        'period': period.id,
                        'date': period.start_date,
                        'lines': [
                            ('create', [{
                                        'debit': Decimal('100'),
                                        'account': receivable.id,
                                        'party': party.id,
                                        }, {
                                        'credit': Decimal('100'),
                                        'account': revenue.id,
                                        }]),
                            ],
                        }])
            company, = self.company.search([
                    ('rec_name', '=', 'Dunder Mifflin'),
                    ])
            payment_term, = self.payment_term.create([{
                        'name': 'Test',
                        'lines': [
                            ('create', [{
                                        'type': 'remainder',
                                        }])
                            ],
                        }])
            field, = self.model_field.search([
                    ('model.model', '=', 'product.template'),
                    ('name', '=', 'account_revenue'),
                    ], limit=1)
            self.property.create([{
                    'field': field.id,
                    'value': str(revenue),
                    'company': company.id,
                    }])
            sale, = self.sale.create([{
                        'party': party.id,
                        'company': company.id,
                        'payment_term': payment_term.id,
                        'currency': company.currency.id,
                        'invoice_address': party.addresses[0].id,
                        'shipment_address': party.addresses[0].id,
                        'lines': [
                            ('create', [{
                                        'description': 'Test',
                                        'quantity': 1,
                                        'unit_price': Decimal('50'),
                                        }]),
                            ],
                        }])
            self.assertEqual(party.credit_amount, Decimal('100'))
            self.sale.quote([sale])
            self.sale.confirm([sale])
            self.assertEqual(party.credit_amount, Decimal('100'))
            # Test limit reaches
            self.assertRaises(UserWarning, self.sale.process, [sale])
            # Increase limit
            party.credit_limit_amount = Decimal('200')
            party.save()
            # process should work
            self.sale.process([sale])
            self.assertEqual(sale.state, 'processing')
            self.assertEqual(party.credit_amount, Decimal('150'))

            # Re-process
            self.sale.process([sale])
            # Decrease limit
            party.credit_limit_amount = Decimal('100')
            party.save()
            # process should still work as sale is already processing
            self.sale.process([sale])


def suite():
    suite = trytond.tests.test_tryton.suite()
    from trytond.modules.account.tests import test_account
    for test in test_account.suite():
        if test not in suite and not isinstance(test, doctest.DocTestCase):
            suite.addTest(test)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        SaleCreditLimitTestCase))
    return suite
