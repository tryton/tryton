# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

from decimal import Decimal
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.pool import Pool
from trytond.exceptions import UserError, UserWarning

from trytond.modules.company.tests import create_company, set_company
from trytond.modules.account.tests import create_chart, get_fiscalyear


class AccountCreditLimitTestCase(ModuleTestCase):
    'Test AccountCreditLimit module'
    module = 'account_credit_limit'
    extras = ['account_dunning']

    @with_transaction()
    def test_check_credit_limit(self):
        'Test check_credit_limit'
        pool = Pool()
        Account = pool.get('account.account')
        Move = pool.get('account.move')
        Journal = pool.get('account.journal')
        Party = pool.get('party.party')

        company = create_company()
        with set_company(company):
            create_chart(company)
            fiscalyear = get_fiscalyear(company)
            fiscalyear.save()
            fiscalyear.create_period([fiscalyear])
            period = fiscalyear.periods[0]

            receivable, = Account.search([
                    ('type.receivable', '=', True),
                    ])
            revenue, = Account.search([
                    ('type.revenue', '=', True),
                    ])
            journal, = Journal.search([], limit=1)
            party, = Party.create([{
                        'name': 'Party',
                        }])
            Move.create([{
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
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        AccountCreditLimitTestCase))
    return suite
