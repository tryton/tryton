#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import sys
import os
DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
import datetime
from decimal import Decimal
import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction


class AccountTestCase(unittest.TestCase):
    '''
    Test Account module.
    '''

    def setUp(self):
        trytond.tests.test_tryton.install_module('account')
        self.account_template = POOL.get('account.account.template')
        self.account = POOL.get('account.account')
        self.account_create_chart = POOL.get(
            'account.create_chart', type='wizard')
        self.company = POOL.get('company.company')
        self.user = POOL.get('res.user')
        self.fiscalyear = POOL.get('account.fiscalyear')
        self.sequence = POOL.get('ir.sequence')
        self.move = POOL.get('account.move')
        self.journal = POOL.get('account.journal')
        self.account_type = POOL.get('account.account.type')

    def test0005views(self):
        '''
        Test views.
        '''
        test_view('account')

    def test0006depends(self):
        '''
        Test depends.
        '''
        test_depends()

    def test0010account_chart(self):
        'Test creation of minimal chart of accounts'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            account_template, = self.account_template.search([
                    ('parent', '=', None),
                    ])
            company, = self.company.search([('name', '=', 'B2CK')])
            self.user.write([self.user(USER)], {
                    'main_company': company.id,
                    'company': company.id,
                    })
            CONTEXT.update(self.user.get_preferences(context_only=True))

            session_id, _, _ = self.account_create_chart.create()
            create_chart = self.account_create_chart(session_id)
            create_chart.account.account_template = account_template
            create_chart.account.company = company
            create_chart.transition_create_account()
            receivable, = self.account.search([
                    ('kind', '=', 'receivable'),
                    ('company', '=', company.id),
                    ])
            payable, = self.account.search([
                    ('kind', '=', 'payable'),
                    ('company', '=', company.id),
                    ])
            create_chart.properties.company = company
            create_chart.properties.account_receivable = receivable
            create_chart.properties.account_payable = payable
            create_chart.transition_create_properties()
            transaction.cursor.commit()

    def test0020fiscalyear(self):
        '''
        Test fiscalyear.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            today = datetime.date.today()
            company, = self.company.search([('name', '=', 'B2CK')])
            sequence = self.sequence.create({
                    'name': '%s' % today.year,
                    'code': 'account.move',
                    'company': company.id,
                    })
            fiscalyear = self.fiscalyear.create({
                    'name': '%s' % today.year,
                    'start_date': today.replace(month=1, day=1),
                    'end_date': today.replace(month=12, day=31),
                    'company': company.id,
                    'post_move_sequence': sequence.id,
                    })
            self.fiscalyear.create_period([fiscalyear])
            self.assertEqual(len(fiscalyear.periods), 12)
            transaction.cursor.commit()

    def test0030account_debit_credit(self):
        '''
        Test account debit/credit.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            fiscalyear, = self.fiscalyear.search([])
            period = fiscalyear.periods[0]
            journal_revenue, = self.journal.search([
                    ('code', '=', 'REV'),
                    ])
            journal_expense, = self.journal.search([
                    ('code', '=', 'EXP'),
                    ])
            revenue, = self.account.search([
                    ('kind', '=', 'revenue'),
                    ])
            receivable, = self.account.search([
                    ('kind', '=', 'receivable'),
                    ])
            expense, = self.account.search([
                    ('kind', '=', 'expense'),
                    ])
            payable, = self.account.search([
                    ('kind', '=', 'payable'),
                    ])
            # Create some moves
            values = [
                {
                    'period': period.id,
                    'journal': journal_revenue.id,
                    'date': period.start_date,
                    'lines': [
                        ('create', {
                                'account': revenue.id,
                                'credit': Decimal(100),
                                }),
                        ('create', {
                                'account': receivable.id,
                                'debit': Decimal(100),
                                }),
                        ],
                    },
                {
                    'period': period.id,
                    'journal': journal_expense.id,
                    'date': period.start_date,
                    'lines': [
                        ('create', {
                                'account': expense.id,
                                'debit': Decimal(30),
                                }),
                        ('create', {
                                'account': payable.id,
                                'credit': Decimal(30),
                                }),
                        ],
                    },
                ]
            for value in values:
                self.move.create(value)

            # Test debit/credit
            self.assertEqual((revenue.debit, revenue.credit),
                (Decimal(0), Decimal(100)))
            self.assertEqual(revenue.balance, Decimal(-100))

            # Use next fiscalyear
            next_sequence = self.sequence.create({
                    'name': 'Next Year',
                    'code': 'account.move',
                    'company': fiscalyear.company.id,
                    })
            next_fiscalyear, = self.fiscalyear.copy([fiscalyear],
                default={
                    'start_date': fiscalyear.end_date + datetime.timedelta(1),
                    'end_date': fiscalyear.end_date + datetime.timedelta(360),
                    'post_move_sequence': next_sequence.id,
                    'periods': None,
                    })
            self.fiscalyear.create_period([next_fiscalyear])

            # Test debit/credit for next year
            with Transaction().set_context(fiscalyear=next_fiscalyear.id):
                revenue = self.account(revenue.id)
                self.assertEqual((revenue.debit, revenue.credit),
                    (Decimal(0), Decimal(0)))
                self.assertEqual(revenue.balance, Decimal(-100))

            # Test debit/credit cumulate for next year
            with Transaction().set_context(fiscalyear=next_fiscalyear.id,
                    cumulate=True):
                revenue = self.account(revenue.id)
                self.assertEqual((revenue.debit, revenue.credit),
                    (Decimal(0), Decimal(100)))
                self.assertEqual(revenue.balance, Decimal(-100))

            # Close fiscalyear
            journal_sequence, = self.sequence.search([
                    ('code', '=', 'account.journal'),
                    ])
            journal_closing = self.journal.create({
                    'name': 'Closing',
                    'code': 'CLO',
                    'type': 'situation',
                    'sequence': journal_sequence.id,
                    })
            type_equity, = self.account_type.search([
                    ('name', '=', 'Equity'),
                    ])
            account_pl = self.account.create({
                    'name': 'P&L',
                    'type': type_equity.id,
                    'deferral': True,
                    'parent': revenue.parent.id,
                    'kind': 'other',
                    })
            self.move.create({
                    'period': fiscalyear.periods[-1].id,
                    'journal': journal_closing.id,
                    'date': fiscalyear.periods[-1].end_date,
                    'lines': [
                        ('create', {
                                'account': revenue.id,
                                'debit': Decimal(100),
                                }),
                        ('create', {
                                'account': expense.id,
                                'credit': Decimal(30),
                                }),
                        ('create', {
                                'account': account_pl.id,
                                'credit': Decimal('70'),
                                }),
                        ],
                    })
            moves = self.move.search([
                    ('state', '=', 'draft'),
                    ('period.fiscalyear', '=', fiscalyear.id),
                    ])
            self.move.post(moves)
            self.fiscalyear.close([fiscalyear])

            # Check deferral
            self.assertEqual(revenue.deferrals, ())

            deferral_receivable, = receivable.deferrals
            self.assertEqual(
                (deferral_receivable.debit, deferral_receivable.credit),
                (Decimal(100), Decimal(0)))
            self.assertEqual(deferral_receivable.fiscalyear, fiscalyear)

            # Test debit/credit
            with Transaction().set_context(fiscalyear=fiscalyear.id):
                revenue = self.account(revenue.id)
                self.assertEqual((revenue.debit, revenue.credit),
                    (Decimal(100), Decimal(100)))
                self.assertEqual(revenue.balance, Decimal(0))

                receivable = self.account(receivable.id)
                self.assertEqual((receivable.debit, receivable.credit),
                    (Decimal(100), Decimal(0)))
                self.assertEqual(receivable.balance, Decimal(100))

            # Test debit/credit for next year
            with Transaction().set_context(fiscalyear=next_fiscalyear.id):
                revenue = self.account(revenue.id)
                self.assertEqual((revenue.debit, revenue.credit),
                    (Decimal(0), Decimal(0)))
                self.assertEqual(revenue.balance, Decimal(0))

                receivable = self.account(receivable.id)
                self.assertEqual((receivable.debit, receivable.credit),
                    (Decimal(0), Decimal(0)))
                self.assertEqual(receivable.balance, Decimal(100))

            # Test debit/credit cumulate for next year
            with Transaction().set_context(fiscalyear=next_fiscalyear.id,
                    cumulate=True):
                revenue = self.account(revenue.id)
                self.assertEqual((revenue.debit, revenue.credit),
                    (Decimal(0), Decimal(0)))
                self.assertEqual(revenue.balance, Decimal(0))

                receivable = self.account(receivable.id)
                self.assertEqual((receivable.debit, receivable.credit),
                    (Decimal(100), Decimal(0)))
                self.assertEqual(receivable.balance, Decimal(100))

            transaction.cursor.rollback()


def suite():
    suite = trytond.tests.test_tryton.suite()
    from trytond.modules.company.tests import test_company
    for test in test_company.suite():
        if test not in suite:
            suite.addTest(test)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        AccountTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
