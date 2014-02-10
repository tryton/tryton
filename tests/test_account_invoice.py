#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import unittest
import doctest
import datetime
from decimal import Decimal
import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, test_view,\
    test_depends, doctest_dropdb
from trytond.transaction import Transaction


class AccountInvoiceTestCase(unittest.TestCase):
    'Test AccountInvoice module'

    def setUp(self):
        trytond.tests.test_tryton.install_module('account_invoice')
        self.payment_term = POOL.get('account.invoice.payment_term')
        self.currency = POOL.get('currency.currency')

    def test0005views(self):
        'Test views'
        test_view('account_invoice')

    def test0006depends(self):
        'Test depends'
        test_depends()

    def test0010payment_term(self):
        'Test payment_term'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            cu1, = self.currency.create([{
                        'name': 'cu1',
                        'symbol': 'cu1',
                        'code': 'cu1'
                        }])

            term, = self.payment_term.create([{
                        'name': '30 days, 1 month, 1 month + 15 days',
                        'lines': [
                            ('create', [{
                                        'sequence': 0,
                                        'type': 'percent',
                                        'divisor': 4,
                                        'percentage': 25,
                                        'days': 30,
                                        }, {
                                        'sequence': 1,
                                        'type': 'percent_on_total',
                                        'divisor': 4,
                                        'percentage': 25,
                                        'months': 1,
                                        }, {
                                        'sequence': 2,
                                        'type': 'fixed',
                                        'months': 1,
                                        'days': 30,
                                        'amount': Decimal('396.84'),
                                        'currency': cu1.id,
                                        }, {
                                        'sequence': 3,
                                        'type': 'remainder',
                                        'months': 2,
                                        'days': 30,
                                        'day': 15,
                                        }])]
                        }])
            terms = term.compute(Decimal('1587.35'), cu1,
                date=datetime.date(2011, 10, 1))
            self.assertEqual(terms, [
                    (datetime.date(2011, 10, 31), Decimal('396.84')),
                    (datetime.date(2011, 11, 01), Decimal('396.84')),
                    (datetime.date(2011, 12, 01), Decimal('396.84')),
                    (datetime.date(2012, 01, 14), Decimal('396.83')),
                    ])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        AccountInvoiceTestCase))
    suite.addTests(doctest.DocFileSuite('scenario_invoice.rst',
            setUp=doctest_dropdb, tearDown=doctest_dropdb, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite('scenario_invoice_supplier.rst',
            setUp=doctest_dropdb, tearDown=doctest_dropdb, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_invoice_alternate_currency.rst',
            setUp=doctest_dropdb, tearDown=doctest_dropdb, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
