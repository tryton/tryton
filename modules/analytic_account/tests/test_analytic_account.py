# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import doctest
from decimal import Decimal
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.tests.test_tryton import doctest_setup, doctest_teardown
from trytond.tests.test_tryton import doctest_checker
from trytond.transaction import Transaction
from trytond.pool import Pool

from trytond.modules.company.tests import create_company, set_company
from trytond.modules.account.tests import create_chart, get_fiscalyear


class AnalyticAccountTestCase(ModuleTestCase):
    'Test AnalyticAccount module'
    module = 'analytic_account'

    @with_transaction()
    def test_account_debit_credit(self):
        'Test account debit/credit'
        pool = Pool()
        Party = pool.get('party.party')
        AnalyticAccount = pool.get('analytic_account.account')
        Journal = pool.get('account.journal')
        Account = pool.get('account.account')
        Move = pool.get('account.move')
        transaction = Transaction()

        party = Party(name='Party')
        party.save()
        company = create_company()
        with set_company(company):
            root, = AnalyticAccount.create([{
                        'type': 'root',
                        'name': 'Root',
                        }])
            analytic_account, = AnalyticAccount.create([{
                        'type': 'normal',
                        'name': 'Analytic Account',
                        'parent': root.id,
                        'root': root.id,
                        }])
            create_chart(company)
            fiscalyear = get_fiscalyear(company)
            fiscalyear.save()
            fiscalyear.create_period([fiscalyear])
            period = fiscalyear.periods[0]
            journal_revenue, = Journal.search([
                    ('code', '=', 'REV'),
                    ])
            journal_expense, = Journal.search([
                    ('code', '=', 'EXP'),
                    ])
            revenue, = Account.search([
                    ('kind', '=', 'revenue'),
                    ])
            receivable, = Account.search([
                    ('kind', '=', 'receivable'),
                    ])
            expense, = Account.search([
                    ('kind', '=', 'expense'),
                    ])
            payable, = Account.search([
                    ('kind', '=', 'payable'),
                    ])

            first_account_line = {
                'account': revenue.id,
                'credit': Decimal(100),
                'analytic_lines': [
                    ('create', [{
                                'account': analytic_account.id,
                                'name': 'Analytic Line',
                                'credit': Decimal(100),
                                'debit': Decimal(0),
                                'journal': journal_revenue.id,
                                'date': period.start_date,
                                }])
                    ]}
            second_account_line = {
                'account': expense.id,
                'debit': Decimal(30),
                'analytic_lines': [
                    ('create', [{
                                'account': analytic_account.id,
                                'name': 'Analytic Line',
                                'debit': Decimal(30),
                                'credit': Decimal(0),
                                'journal': journal_expense.id,
                                'date': period.start_date,
                                }])
                    ]}
            # Create some moves
            vlist = [{
                    'period': period.id,
                    'journal': journal_revenue.id,
                    'date': period.start_date,
                    'lines': [
                        ('create', [first_account_line, {
                                    'account': receivable.id,
                                    'debit': Decimal(100),
                                    'party': party.id,
                                    }]),
                        ],
                    }, {
                    'period': period.id,
                    'journal': journal_expense.id,
                    'date': period.start_date,
                    'lines': [
                        ('create', [second_account_line, {
                                    'account': payable.id,
                                    'credit': Decimal(30),
                                    'party': party.id,
                                    }]),
                        ],
                    },
                ]
            Move.create(vlist)

            self.assertEqual((analytic_account.debit, analytic_account.credit),
                (Decimal(30), Decimal(100)))
            self.assertEqual(analytic_account.balance, Decimal(70))

            with transaction.set_context(start_date=period.end_date):
                analytic_account = AnalyticAccount(analytic_account.id)
                self.assertEqual((analytic_account.debit,
                        analytic_account.credit),
                    (Decimal(0), Decimal(0)))
                self.assertEqual(analytic_account.balance, Decimal(0))

            with transaction.set_context(end_date=period.end_date):
                analytic_account = AnalyticAccount(analytic_account.id)
                self.assertEqual((analytic_account.debit,
                        analytic_account.credit),
                    (Decimal(30), Decimal(100)))
                self.assertEqual(analytic_account.balance, Decimal(70))


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        AnalyticAccountTestCase))
    suite.addTests(doctest.DocFileSuite('scenario_analytic_account.rst',
            setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
