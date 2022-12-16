# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import doctest
import datetime
from decimal import Decimal
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.tests.test_tryton import doctest_setup, doctest_teardown
from trytond.tests.test_tryton import doctest_checker
from trytond.pool import Pool

from trytond.modules.currency.tests import create_currency


def set_invoice_sequences(fiscalyear):
    pool = Pool()
    Sequence = pool.get('ir.sequence.strict')

    sequence = Sequence(name=fiscalyear.name, code='account.invoice')
    sequence.company = fiscalyear.company
    sequence.save()
    for type_ in ['out', 'in']:
        for invoice in ['invoice', 'credit_note']:
            name = '%s_%s_sequence' % (type_, invoice)
            setattr(fiscalyear, name, sequence)
    return fiscalyear


class AccountInvoiceTestCase(ModuleTestCase):
    'Test AccountInvoice module'
    module = 'account_invoice'

    @with_transaction()
    def test_payment_term(self):
        'Test payment_term'
        pool = Pool()
        PaymentTerm = pool.get('account.invoice.payment_term')

        cu1 = create_currency('cu1')
        term, = PaymentTerm.create([{
                    'name': '30 days, 1 month, 1 month + 15 days',
                    'lines': [
                        ('create', [{
                                    'sequence': 0,
                                    'type': 'percent',
                                    'divisor': 4,
                                    'ratio': Decimal('.25'),
                                    'relativedeltas': [('create', [{
                                                    'days': 30,
                                                    },
                                                ]),
                                        ],
                                    }, {
                                    'sequence': 1,
                                    'type': 'percent_on_total',
                                    'divisor': 4,
                                    'ratio': Decimal('.25'),
                                    'relativedeltas': [('create', [{
                                                    'months': 1,
                                                    },
                                                ]),
                                        ],
                                    }, {
                                    'sequence': 2,
                                    'type': 'fixed',
                                    'amount': Decimal('396.84'),
                                    'currency': cu1.id,
                                    'relativedeltas': [('create', [{
                                                    'months': 1,
                                                    'days': 30,
                                                    },
                                                ]),
                                        ],
                                    }, {
                                    'sequence': 3,
                                    'type': 'remainder',
                                    'relativedeltas': [('create', [{
                                                    'months': 2,
                                                    'days': 30,
                                                    'day': 15,
                                                    },
                                                ]),
                                        ],
                                    }])]
                    }])
        terms = term.compute(Decimal('1587.35'), cu1,
            date=datetime.date(2011, 10, 1))
        self.assertEqual(terms, [
                (datetime.date(2011, 10, 31), Decimal('396.84')),
                (datetime.date(2011, 11, 1), Decimal('396.84')),
                (datetime.date(2011, 12, 1), Decimal('396.84')),
                (datetime.date(2012, 1, 14), Decimal('396.83')),
                ])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        AccountInvoiceTestCase))
    suite.addTests(doctest.DocFileSuite('scenario_invoice.rst',
            setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite('scenario_invoice_supplier.rst',
            setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_invoice_alternate_currency.rst',
            setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
