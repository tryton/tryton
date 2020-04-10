# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import doctest
import datetime
from decimal import Decimal
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.tests.test_tryton import doctest_teardown
from trytond.tests.test_tryton import doctest_checker
from trytond.pool import Pool

from ..exceptions import PaymentTermValidationError
from trytond.modules.currency.tests import create_currency


def set_invoice_sequences(fiscalyear):
    pool = Pool()
    Sequence = pool.get('ir.sequence.strict')
    InvoiceSequence = pool.get('account.fiscalyear.invoice_sequence')

    sequence = Sequence(name=fiscalyear.name, code='account.invoice')
    sequence.company = fiscalyear.company
    sequence.save()
    fiscalyear.invoice_sequences = []
    invoice_sequence = InvoiceSequence()
    invoice_sequence.fiscalyear = fiscalyear
    invoice_sequence.in_invoice_sequence = sequence
    invoice_sequence.in_credit_note_sequence = sequence
    invoice_sequence.out_invoice_sequence = sequence
    invoice_sequence.out_credit_note_sequence = sequence
    invoice_sequence.save()
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

    @with_transaction()
    def test_payment_term_with_repeating_decimal(self):
        "Test payment_term with repeating decimal"
        pool = Pool()
        PaymentTerm = pool.get('account.invoice.payment_term')

        PaymentTerm.create([{
                    'name': "Repeating Decimal",
                    'lines': [
                        ('create', [{
                                    'type': 'percent',
                                    'divisor': Decimal(3),
                                    'ratio': Decimal('0.3333333333'),
                                    }, {
                                    'type': 'remainder',
                                    }]),
                        ],
                    }])

    @with_transaction()
    def test_payment_term_with_invalid_ratio_divisor(self):
        "Test payment_term with invalid ratio and divisor"
        pool = Pool()
        PaymentTerm = pool.get('account.invoice.payment_term')

        with self.assertRaises(PaymentTermValidationError):
            PaymentTerm.create([{
                        'name': "Invalid ratio and divisor",
                        'lines': [
                            ('create', [{
                                        'type': 'percent',
                                        'divisor': Decimal(2),
                                        'ratio': Decimal('0.4'),
                                        }, {
                                        'type': 'remainder',
                                        }]),
                            ],
                        }])

    @with_transaction()
    def test_payment_term_with_empty_value(self):
        'Test payment_term with empty'
        pool = Pool()
        PaymentTerm = pool.get('account.invoice.payment_term')

        cu1 = create_currency('cu1')
        remainder_term, percent_term = PaymentTerm.create([{
                    'name': 'Remainder',
                    'lines': [
                        ('create', [{'type': 'remainder',
                                    'relativedeltas': [('create', [{
                                                    'months': 1,
                                                    },
                                                ]),
                                        ],
                                    }])]
                    }, {
                    'name': '25% tomorrow, remainder un month later ',
                    'lines': [
                        ('create', [{'type': 'percent',
                                    'divisor': 4,
                                    'ratio': Decimal('.25'),
                                    'relativedeltas': [('create', [{
                                                    'days': 1,
                                                    },
                                                ]),
                                        ],
                                    }, {'type': 'remainder',
                                    'relativedeltas': [('create', [{
                                                    'months': 1,
                                                    },
                                                ]),
                                        ],
                                    }])]
                    }])
        terms = remainder_term.compute(Decimal('0.0'), cu1,
            date=datetime.date(2016, 5, 17))
        self.assertEqual(terms, [
                (datetime.date(2016, 5, 17), Decimal('0.0')),
                ])
        terms = percent_term.compute(Decimal('0.0'), cu1,
            date=datetime.date(2016, 5, 17))
        self.assertEqual(terms, [
                (datetime.date(2016, 5, 17), Decimal('0.0')),
                ])

    @with_transaction()
    def test_negative_amount(self):
        'Test payment term with negative amount'
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
                                    'amount': Decimal('4.0'),
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
        terms = term.compute(Decimal('-10.00'), cu1,
            date=datetime.date(2011, 10, 1))
        self.assertListEqual(terms, [
                (datetime.date(2011, 10, 31), Decimal('-2.5')),
                (datetime.date(2011, 11, 1), Decimal('-2.5')),
                (datetime.date(2011, 12, 1), Decimal('-4.0')),
                (datetime.date(2012, 1, 14), Decimal('-1.0')),
                ])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        AccountInvoiceTestCase))
    suite.addTests(doctest.DocFileSuite('scenario_invoice.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite('scenario_invoice_supplier.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite('scenario_invoice_with_credit.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_invoice_supplier_post_paid.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite('scenario_credit_note.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_invoice_customer_sequential.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_invoice_overpayment.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_invoice_alternate_currency.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_invoice_alternate_currency_lower_rate.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite('scenario_invoice_group_line.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_renew_fiscalyear.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
