# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import doctest

from decimal import Decimal
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction
from trytond.exceptions import UserError, UserWarning


class AccountCreditLimitTestCase(ModuleTestCase):
    'Test AccountCreditLimit module'
    module = 'account_credit_limit'

    def setUp(self):
        super(AccountCreditLimitTestCase, self).setUp()
        self.account = POOL.get('account.account')
        self.move = POOL.get('account.move')
        self.period = POOL.get('account.period')
        self.journal = POOL.get('account.journal')
        self.party = POOL.get('party.party')

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
                        }])
            self.move.create([{
                        'journal': journal.id,
                        'period': period.id,
                        'date': period.start_date,
                        'lines': [
                            ('create', [{
                                        'debit': Decimal(100),
                                        'account': receivable.id,
                                        'party': party.id,
                                        }, {
                                        'credit': Decimal(100),
                                        'account': revenue.id,
                                        }]),
                            ],
                        }])
            self.assertEqual(party.credit_amount, Decimal(100))
            self.assertEqual(party.credit_limit_amount, None)
            party.check_credit_limit(Decimal(0))
            party.check_credit_limit(Decimal(0), 'test')
            party.check_credit_limit(Decimal(100))
            party.check_credit_limit(Decimal(100), 'test')
            party.credit_limit_amount = Decimal(0)
            party.save()
            self.assertRaises(UserError, party.check_credit_limit,
                Decimal(0))
            self.assertRaises(UserWarning, party.check_credit_limit,
                Decimal(0), 'test')
            party.credit_limit_amount = Decimal(200)
            party.save()
            party.check_credit_limit(Decimal(0))
            party.check_credit_limit(Decimal(0), 'test')
            self.assertRaises(UserError, party.check_credit_limit,
                Decimal(150))
            self.assertRaises(UserWarning, party.check_credit_limit,
                Decimal(150), 'test')


def suite():
    suite = trytond.tests.test_tryton.suite()
    from trytond.modules.account.tests import test_account
    for test in test_account.suite():
        if test not in suite and not isinstance(test, doctest.DocTestCase):
            suite.addTest(test)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        AccountCreditLimitTestCase))
    return suite
