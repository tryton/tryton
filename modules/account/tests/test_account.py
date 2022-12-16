# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import doctest
import datetime
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from trytond.pool import Pool
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.tests.test_tryton import doctest_teardown
from trytond.tests.test_tryton import doctest_checker
from trytond.transaction import Transaction
from trytond.exceptions import UserError

from trytond.modules.company.tests import create_company, set_company
from trytond.modules.account.tax import TaxableMixin
from trytond.modules.currency.tests import create_currency


def create_chart(company, tax=False, chart='account.account_template_root_en'):
    pool = Pool()
    AccountTemplate = pool.get('account.account.template')
    TaxTemplate = pool.get('account.tax.template')
    TaxCodeTemplate = pool.get('account.tax.code.template')
    ModelData = pool.get('ir.model.data')
    CreateChart = pool.get('account.create_chart', type='wizard')
    Account = pool.get('account.account')

    module, xml_id = chart.split('.')
    template = AccountTemplate(ModelData.get_id(module, xml_id))
    if tax:
        tax_account = AccountTemplate(ModelData.get_id(
                'account', 'account_template_tax_en'))
        with Transaction().set_user(0):
            tax = TaxTemplate()
            tax.name = tax.description = '20% VAT'
            tax.type = 'percentage'
            tax.rate = Decimal('0.2')
            tax.account = template
            tax.invoice_account = tax_account
            tax.credit_note_account = tax_account
            tax.save()

            TaxCodeTemplate.create([{
                        'name': 'Tax Code',
                        'account': template,
                        'lines': [('create', [{
                                        'operator': '+',
                                        'type': 'invoice',
                                        'amount': 'tax',
                                        'tax': tax.id,
                                        }])],
                        }, {
                        'name': 'Base Code',
                        'account': template,
                        'lines': [('create', [{
                                        'operator': '+',
                                        'type': 'invoice',
                                        'amount': 'base',
                                        'tax': tax.id,
                                        }])],
                        }])

    session_id, _, _ = CreateChart.create()
    create_chart = CreateChart(session_id)
    create_chart.account.account_template = template
    create_chart.account.company = company
    create_chart.transition_create_account()
    receivable, = Account.search([
            ('type.receivable', '=', True),
            ('company', '=', company.id),
            ], limit=1)
    payable, = Account.search([
            ('type.payable', '=', True),
            ('company', '=', company.id),
            ], limit=1)
    create_chart.properties.company = company
    create_chart.properties.account_receivable = receivable
    create_chart.properties.account_payable = payable
    create_chart.transition_create_properties()


def get_fiscalyear(company, today=None, start_date=None, end_date=None):
    pool = Pool()
    Sequence = pool.get('ir.sequence')
    FiscalYear = pool.get('account.fiscalyear')

    if not today:
        today = datetime.date.today()
    if not start_date:
        start_date = today.replace(month=1, day=1)
    if not end_date:
        end_date = today.replace(month=12, day=31)

    sequence, = Sequence.create([{
                'name': '%s' % today.year,
                'code': 'account.move',
                'company': company.id,
                }])
    fiscalyear = FiscalYear(name='%s' % today.year, company=company)
    fiscalyear.start_date = start_date
    fiscalyear.end_date = end_date
    fiscalyear.post_move_sequence = sequence
    return fiscalyear


def close_fiscalyear(fiscalyear):
    pool = Pool()
    Sequence = pool.get('ir.sequence')
    Journal = pool.get('account.journal')
    Period = pool.get('account.period')
    AccountType = pool.get('account.account.type')
    Account = pool.get('account.account')
    Move = pool.get('account.move')
    FiscalYear = pool.get('account.fiscalyear')
    BalanceNonDeferral = pool.get(
        'account.fiscalyear.balance_non_deferral', type='wizard')

    # Balance non-deferral
    journal_sequence, = Sequence.search([
            ('code', '=', 'account.journal'),
            ])
    journal_closing, = Journal.create([{
                'name': 'Closing',
                'code': 'CLO',
                'type': 'situation',
                'sequence': journal_sequence.id,
                }])
    period_closing, = Period.create([{
                'name': 'Closing',
                'start_date': fiscalyear.end_date,
                'end_date': fiscalyear.end_date,
                'fiscalyear': fiscalyear.id,
                'type': 'adjustment',
                }])
    type_equity, = AccountType.search([
            ('name', '=', 'Equity'),
            ])
    revenue, = Account.search([
            ('type.revenue', '=', True),
            ])
    account_pl, = Account.create([{
                'name': 'P&L',
                'type': type_equity.id,
                'parent': revenue.parent.id,
                }])

    session_id = BalanceNonDeferral.create()[0]
    balance_non_deferral = BalanceNonDeferral(session_id)

    balance_non_deferral.start.fiscalyear = fiscalyear
    balance_non_deferral.start.journal = journal_closing
    balance_non_deferral.start.period = period_closing
    balance_non_deferral.start.credit_account = account_pl
    balance_non_deferral.start.debit_account = account_pl

    balance_non_deferral._execute('balance')

    moves = Move.search([
            ('state', '=', 'draft'),
            ('period.fiscalyear', '=', fiscalyear.id),
            ])
    Move.post(moves)

    # Close fiscalyear
    FiscalYear.close([fiscalyear])


class AccountTestCase(ModuleTestCase):
    'Test Account module'
    module = 'account'

    @with_transaction()
    def test_account_chart(self):
        'Test creation and update of minimal chart of accounts'
        pool = Pool()
        Account = pool.get('account.account')
        Tax = pool.get('account.tax')
        UpdateChart = pool.get('account.update_chart', type='wizard')

        company = create_company()
        with set_company(company):
            create_chart(company, tax=True)
            root, = Account.search([('parent', '=', None)])

            # Create an account and tax without template

            cash, = Account.search([('name', '=', 'Main Cash')])
            Account.copy([cash.id])

            tax, = Tax.search([])
            Tax.copy([tax.id])

            session_id, _, _ = UpdateChart.create()
            update_chart = UpdateChart(session_id)
            update_chart.start.account = root
            update_chart.transition_update()

    @with_transaction()
    def test_fiscalyear(self):
        'Test fiscalyear'
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')
        company = create_company()
        with set_company(company):
            fiscalyear = get_fiscalyear(company)
            fiscalyear.save()
            FiscalYear.create_period([fiscalyear])
            self.assertEqual(len(fiscalyear.periods), 12)

    @with_transaction()
    def test_fiscalyear_create_periods(self):
        'Test fiscalyear create periods'
        FiscalYear = Pool().get('account.fiscalyear')

        company = create_company()
        with set_company(company):
            year = datetime.date.today().year
            date = datetime.date
            for start_date, end_date, interval, end_day, num_periods in [
                    (date(year, 1, 1), date(year, 12, 31), 1, 31, 12),
                    (date(year + 1, 1, 1), date(year + 1, 12, 31), 3, 31, 4),
                    (date(year + 2, 1, 1), date(year + 2, 12, 31), 5, 31, 3),
                    (date(year + 3, 4, 6), date(year + 4, 4, 5), 1, 5, 12),
                    (date(year + 4, 4, 6), date(year + 5, 4, 5), 3, 5, 4),
                    (date(year + 5, 4, 6), date(year + 6, 4, 5), 5, 5, 3),
                    (date(year + 6, 6, 6), date(year + 6, 12, 31), 1, 29, 8),
                    (date(year + 7, 7, 7), date(year + 7, 12, 31), 3, 29, 3),
                    (date(year + 8, 1, 1), date(year + 9, 8, 7), 1, 29, 20),
                    (date(year + 9, 9, 9), date(year + 10, 11, 12), 3, 29, 5),
                    ]:
                fiscalyear = get_fiscalyear(
                    company, start_date, start_date, end_date)
                fiscalyear.save()
                FiscalYear.create_period([fiscalyear], interval, end_day)

                self.assertEqual(len(fiscalyear.periods), num_periods)

                self.assertEqual(fiscalyear.periods[-1].end_date, end_date)
                self.assertTrue(all(
                    p.end_date == p.end_date + relativedelta(day=end_day)
                    for p in fiscalyear.periods[:-1]))

                self.assertEqual(fiscalyear.periods[0].start_date, start_date)
                self.assertTrue(all(
                    p1.end_date + relativedelta(days=1) == p2.start_date
                    for p1, p2 in zip(
                        fiscalyear.periods[:-1], fiscalyear.periods[1:])))

    @with_transaction()
    def test_account_debit_credit(self):
        'Test account debit/credit'
        pool = Pool()
        Party = pool.get('party.party')
        FiscalYear = pool.get('account.fiscalyear')
        Journal = pool.get('account.journal')
        Account = pool.get('account.account')
        Move = pool.get('account.move')

        party = Party(name='Party')
        party.save()

        company = create_company()
        with set_company(company):
            fiscalyear = get_fiscalyear(company)
            fiscalyear.save()
            FiscalYear.create_period([fiscalyear])
            period = fiscalyear.periods[0]
            create_chart(company)

            sec_cur = create_currency('sec')

            journal_revenue, = Journal.search([
                    ('code', '=', 'REV'),
                    ])
            journal_expense, = Journal.search([
                    ('code', '=', 'EXP'),
                    ])
            revenue, = Account.search([
                    ('type.revenue', '=', True),
                    ])
            receivable, = Account.search([
                    ('type.receivable', '=', True),
                    ])
            expense, = Account.search([
                    ('type.expense', '=', True),
                    ])
            payable, = Account.search([
                    ('type.payable', '=', True),
                    ])
            cash, = Account.search([
                    ('name', '=', 'Main Cash'),
                    ])
            cash_cur, = Account.copy([cash], default={
                    'second_currency': sec_cur.id,
                    })
            # Create some moves
            vlist = [
                {
                    'period': period.id,
                    'journal': journal_revenue.id,
                    'date': period.start_date,
                    'lines': [
                        ('create', [{
                                    'account': revenue.id,
                                    'credit': Decimal(100),
                                    }, {
                                    'account': receivable.id,
                                    'debit': Decimal(100),
                                    'party': party.id,
                                    }]),
                        ],
                    },
                {
                    'period': period.id,
                    'journal': journal_revenue.id,
                    'date': period.start_date,
                    'lines': [
                        ('create', [{
                                    'account': receivable.id,
                                    'credit': Decimal(80),
                                    'second_currency': sec_cur.id,
                                    'amount_second_currency': -Decimal(50),
                                    'party': party.id,
                                    }, {
                                    'account': cash_cur.id,
                                    'debit': Decimal(80),
                                    'second_currency': sec_cur.id,
                                    'amount_second_currency': Decimal(50),
                                    }]),
                        ],
                    },
                {
                    'period': period.id,
                    'journal': journal_expense.id,
                    'date': period.start_date,
                    'lines': [
                        ('create', [{
                                    'account': expense.id,
                                    'debit': Decimal(30),
                                    }, {
                                    'account': payable.id,
                                    'credit': Decimal(30),
                                    'party': party.id,
                                    }]),
                        ],
                    },
                ]
            Move.create(vlist)

            # Test debit/credit
            self.assertEqual((revenue.debit, revenue.credit),
                (Decimal(0), Decimal(100)))
            self.assertEqual(revenue.balance, Decimal(-100))

            self.assertEqual((cash_cur.debit, cash_cur.credit),
                (Decimal(80), Decimal(0)))
            self.assertEqual(
                cash_cur.amount_second_currency, Decimal(50))

            # Use next fiscalyear
            today = datetime.date.today()
            next_fiscalyear = get_fiscalyear(company,
                today=today.replace(year=today.year + 1))
            next_fiscalyear.save()
            FiscalYear.create_period([next_fiscalyear])

            # Test debit/credit for next year
            with Transaction().set_context(fiscalyear=next_fiscalyear.id):
                revenue = Account(revenue.id)
                self.assertEqual((revenue.debit, revenue.credit),
                    (Decimal(0), Decimal(0)))
                self.assertEqual(revenue.balance, Decimal(-100))

                cash_cur = Account(cash_cur.id)
                self.assertEqual(
                    cash_cur.amount_second_currency, Decimal(50))

            # Test debit/credit cumulate for next year
            with Transaction().set_context(fiscalyear=next_fiscalyear.id,
                    cumulate=True):
                revenue = Account(revenue.id)
                self.assertEqual((revenue.debit, revenue.credit),
                    (Decimal(0), Decimal(100)))
                self.assertEqual(revenue.balance, Decimal(-100))

                cash_cur = Account(cash_cur.id)
                self.assertEqual(
                    cash_cur.amount_second_currency, Decimal(50))

            close_fiscalyear(fiscalyear)

            # Check deferral
            self.assertEqual(revenue.deferrals, ())

            deferral_receivable, = receivable.deferrals
            self.assertEqual(
                (deferral_receivable.debit, deferral_receivable.credit),
                (Decimal(100), Decimal(80)))
            self.assertEqual(deferral_receivable.fiscalyear, fiscalyear)

            cash_cur = Account(cash_cur.id)
            deferral_cash_cur, = cash_cur.deferrals
            self.assertEqual(
                deferral_cash_cur.amount_second_currency, Decimal(50))

            # Test debit/credit
            with Transaction().set_context(fiscalyear=fiscalyear.id):
                revenue = Account(revenue.id)
                self.assertEqual((revenue.debit, revenue.credit),
                    (Decimal(100), Decimal(100)))
                self.assertEqual(revenue.balance, Decimal(0))

                receivable = Account(receivable.id)
                self.assertEqual((receivable.debit, receivable.credit),
                    (Decimal(100), Decimal(80)))
                self.assertEqual(receivable.balance, Decimal(20))

                cash_cur = Account(cash_cur.id)
                self.assertEqual(
                    cash_cur.amount_second_currency, Decimal(50))

            # Test debit/credit for next year
            with Transaction().set_context(fiscalyear=next_fiscalyear.id):
                revenue = Account(revenue.id)
                self.assertEqual((revenue.debit, revenue.credit),
                    (Decimal(0), Decimal(0)))
                self.assertEqual(revenue.balance, Decimal(0))

                receivable = Account(receivable.id)
                self.assertEqual((receivable.debit, receivable.credit),
                    (Decimal(0), Decimal(0)))
                self.assertEqual(receivable.balance, Decimal(20))

                cash_cur = Account(cash_cur.id)
                self.assertEqual(
                    cash_cur.amount_second_currency, Decimal(50))

            # Test debit/credit cumulate for next year
            with Transaction().set_context(fiscalyear=next_fiscalyear.id,
                    cumulate=True):
                revenue = Account(revenue.id)
                self.assertEqual((revenue.debit, revenue.credit),
                    (Decimal(0), Decimal(0)))
                self.assertEqual(revenue.balance, Decimal(0))

                receivable = Account(receivable.id)
                self.assertEqual((receivable.debit, receivable.credit),
                    (Decimal(100), Decimal(80)))
                self.assertEqual(receivable.balance, Decimal(20))

                cash_cur = Account(cash_cur.id)
                self.assertEqual(
                    cash_cur.amount_second_currency, Decimal(50))

    @with_transaction()
    def test_account_type_amount(self):
        "Test account type amount"
        pool = Pool()
        Party = pool.get('party.party')
        FiscalYear = pool.get('account.fiscalyear')
        Journal = pool.get('account.journal')
        Account = pool.get('account.account')
        Move = pool.get('account.move')
        Type = pool.get('account.account.type')

        party = Party(name='Party')
        party.save()

        company = create_company()
        with set_company(company):
            fiscalyear = get_fiscalyear(company)
            fiscalyear.save()
            FiscalYear.create_period([fiscalyear])
            period = fiscalyear.periods[0]
            create_chart(company)

            journal_revenue, = Journal.search([
                    ('code', '=', 'REV'),
                    ])
            revenue, = Account.search([
                    ('type.revenue', '=', True),
                    ])
            receivable, = Account.search([
                    ('type.receivable', '=', True),
                    ])

            Move.create([{
                        'period': period.id,
                        'journal': journal_revenue.id,
                        'date': period.start_date,
                        'lines': [
                            ('create', [{
                                        'account': revenue.id,
                                        'credit': Decimal(100),
                                        }, {
                                        'account': receivable.id,
                                        'debit': Decimal(100),
                                        'party': party.id,
                                        }]),
                            ],
                        }])

            with Transaction().set_context(fiscalyear=fiscalyear.id):
                revenue_type = Type(revenue.type)
                receivable_type = Type(receivable.type)

            # Test type amount
            self.assertEqual(revenue_type.amount, Decimal(100))
            self.assertEqual(receivable_type.amount, Decimal(100))

            # Set a debit type on receivable
            with Transaction().set_context(fiscalyear=fiscalyear.id):
                debit_receivable_type, = Type.copy([receivable_type])
            receivable.debit_type = debit_receivable_type
            receivable.save()
            self.assertEqual(receivable_type.amount, Decimal(0))
            self.assertEqual(debit_receivable_type.amount, Decimal(100))

            # Set a debit type on revenue
            with Transaction().set_context(fiscalyear=fiscalyear.id):
                debit_revenue_type, = Type.copy([revenue_type])
            revenue.debit_type = debit_revenue_type
            revenue.save()
            self.assertEqual(revenue_type.amount, Decimal(100))
            self.assertEqual(debit_revenue_type.amount, Decimal(0))

    @with_transaction()
    def test_move_post(self):
        "Test posting move"
        pool = Pool()
        Party = pool.get('party.party')
        FiscalYear = pool.get('account.fiscalyear')
        Journal = pool.get('account.journal')
        Account = pool.get('account.account')
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Period = pool.get('account.period')

        party = Party(name='Party')
        party.save()

        company = create_company()
        with set_company(company):
            fiscalyear = get_fiscalyear(company)
            fiscalyear.save()
            FiscalYear.create_period([fiscalyear])
            period = fiscalyear.periods[0]
            create_chart(company)

            journal_revenue, = Journal.search([
                    ('code', '=', 'REV'),
                    ])
            revenue, = Account.search([
                    ('type.revenue', '=', True),
                    ])
            receivable, = Account.search([
                    ('type.receivable', '=', True),
                    ])

            move = Move()
            move.period = period
            move.journal = journal_revenue
            move.date = period.start_date
            move.lines = [
                Line(account=revenue, credit=Decimal(100)),
                Line(account=receivable, debit=Decimal(100), party=party),
                ]
            move.save()
            Move.post([move])
            move_id = move.id

            self.assertEqual(move.state, 'posted')

            # Can not post an empty move
            with self.assertRaises(UserError):
                move = Move()
                move.period = period
                move.journal = journal_revenue
                move.date = period.start_date
                move.save()
                Move.post([move])
            Move.delete([move])

            # Can not modify posted move
            with self.assertRaises(UserError):
                move = Move(move_id)
                move.date = period.end_date
                move.save()

            # Can not go back to draft
            with self.assertRaises(UserError):
                move = Move(move_id)
                move.state = 'draft'
                move.save()

            Period.close([period])

            # Can not create move with lines on closed period
            with self.assertRaises(UserError):
                move = Move()
                move.period = period
                move.journal = journal_revenue
                move.date = period.start_date
                move.lines = [
                    Line(account=revenue, credit=Decimal(100)),
                    Line(account=receivable, debit=Decimal(100), party=party),
                    ]
                move.save()

    @with_transaction()
    def test_tax_compute(self):
        'Test tax compute/reverse_compute'
        pool = Pool()
        Account = pool.get('account.account')
        Tax = pool.get('account.tax')
        today = datetime.date.today()

        company = create_company()
        with set_company(company):
            create_chart(company)

            tax_account, = Account.search([
                    ('name', '=', 'Main Tax'),
                    ])
            tax = Tax()
            tax.name = tax.description = 'Test'
            tax.type = 'none'
            tax.invoice_account = tax_account
            tax.credit_note_account = tax_account

            child1 = Tax()
            child1.name = child1.description = 'Child 1'
            child1.type = 'percentage'
            child1.rate = Decimal('0.2')
            child1.invoice_account = tax_account
            child1.credit_note_account = tax_account
            child1.save()

            child2 = Tax()
            child2.name = child2.description = 'Child 1'
            child2.type = 'fixed'
            child2.amount = Decimal('10')
            child2.invoice_account = tax_account
            child2.credit_note_account = tax_account
            child2.save()

            tax.childs = [child1, child2]
            tax.save()

            self.assertEqual(Tax.compute([tax], Decimal('100'), 2),
                [{
                        'base': Decimal('200'),
                        'amount': Decimal('40.0'),
                        'tax': child1,
                        }, {
                        'base': Decimal('200'),
                        'amount': Decimal('20'),
                        'tax': child2,
                        }])

            self.assertEqual(
                Tax.reverse_compute(Decimal('130'), [tax]),
                Decimal('100'))

            child1.end_date = today + relativedelta(days=5)
            child1.save()
            self.assertEqual(Tax.compute([tax], Decimal('100'), 2, today),
                [{
                        'base': Decimal('200'),
                        'amount': Decimal('40.0'),
                        'tax': child1,
                        }, {
                        'base': Decimal('200'),
                        'amount': Decimal('20'),
                        'tax': child2,
                        }])

            self.assertEqual(
                Tax.reverse_compute(Decimal('130'), [tax], today),
                Decimal('100'))

            child1.start_date = today + relativedelta(days=1)
            child1.save()
            self.assertEqual(Tax.compute([tax], Decimal('100'), 2, today),
                [{
                        'base': Decimal('200'),
                        'amount': Decimal('20'),
                        'tax': child2,
                        }])
            self.assertEqual(
                Tax.reverse_compute(Decimal('110'), [tax], today),
                Decimal('100'))
            self.assertEqual(Tax.compute([tax], Decimal('100'), 2,
                    today + relativedelta(days=1)), [{
                        'base': Decimal('200'),
                        'amount': Decimal('40.0'),
                        'tax': child1,
                        }, {
                        'base': Decimal('200'),
                        'amount': Decimal('20'),
                        'tax': child2,
                        }])
            self.assertEqual(
                Tax.reverse_compute(
                    Decimal('130'), [tax], today + relativedelta(days=1)),
                Decimal('100'))
            self.assertEqual(Tax.compute([tax], Decimal('100'), 2,
                    today + relativedelta(days=5)), [{
                        'base': Decimal('200'),
                        'amount': Decimal('40.0'),
                        'tax': child1,
                        }, {
                        'base': Decimal('200'),
                        'amount': Decimal('20'),
                        'tax': child2,
                        }])
            self.assertEqual(
                Tax.reverse_compute(Decimal('130'), [tax],
                    today + relativedelta(days=5)),
                Decimal('100'))
            self.assertEqual(Tax.compute([tax], Decimal('100'), 2,
                    today + relativedelta(days=6)), [{
                        'base': Decimal('200'),
                        'amount': Decimal('20'),
                        'tax': child2,
                        }])
            self.assertEqual(
                Tax.reverse_compute(Decimal('110'), [tax],
                    today + relativedelta(days=6)),
                Decimal('100'))

            child1.end_date = None
            child1.save()
            self.assertEqual(Tax.compute([tax], Decimal('100'), 2,
                    today + relativedelta(days=6)), [{
                        'base': Decimal('200'),
                        'amount': Decimal('40.0'),
                        'tax': child1,
                        }, {
                        'base': Decimal('200'),
                        'amount': Decimal('20'),
                        'tax': child2,
                        }])
            self.assertEqual(
                Tax.reverse_compute(Decimal('130'), [tax],
                    today + relativedelta(days=6)),
                Decimal('100'))

            ecotax1 = Tax()
            ecotax1.name = ecotax1.description = 'EcoTax 1'
            ecotax1.type = 'fixed'
            ecotax1.amount = Decimal(5)
            ecotax1.invoice_account = tax_account
            ecotax1.credit_note_account = tax_account
            ecotax1.sequence = 10
            ecotax1.save()

            vat0 = Tax()
            vat0.name = vat0.description = 'VAT0'
            vat0.type = 'percentage'
            vat0.rate = Decimal('0.1')
            vat0.invoice_account = tax_account
            vat0.credit_note_account = tax_account
            vat0.sequence = 5
            vat0.save()

            vat1 = Tax()
            vat1.name = vat1.description = 'VAT1'
            vat1.type = 'percentage'
            vat1.rate = Decimal('0.2')
            vat1.invoice_account = tax_account
            vat1.credit_note_account = tax_account
            vat1.sequence = 20
            vat1.save()

            self.assertEqual(
                Tax.compute([vat0, ecotax1, vat1], Decimal(100), 1),
                [{
                        'base': Decimal(100),
                        'amount': Decimal(10),
                        'tax': vat0,
                        }, {
                        'base': Decimal(100),
                        'amount': Decimal(5),
                        'tax': ecotax1,
                        }, {
                        'base': Decimal(100),
                        'amount': Decimal(20),
                        'tax': vat1,
                        }])
            self.assertEqual(
                Tax.reverse_compute(Decimal(135), [vat0, ecotax1, vat1]),
                Decimal(100))

    @with_transaction()
    def test_tax_compute_with_update_unit_price(self):
        'Test tax compute with unit_price modifying tax'
        pool = Pool()
        Account = pool.get('account.account')
        Tax = pool.get('account.tax')

        company = create_company()
        with set_company(company):
            create_chart(company)

            tax_account, = Account.search([
                    ('name', '=', 'Main Tax'),
                    ])
            ecotax1 = Tax()
            ecotax1.name = ecotax1.description = 'EcoTax 1'
            ecotax1.type = 'fixed'
            ecotax1.amount = Decimal(5)
            ecotax1.invoice_account = tax_account
            ecotax1.credit_note_account = tax_account
            ecotax1.update_unit_price = True
            ecotax1.sequence = 10
            ecotax1.save()

            vat1 = Tax()
            vat1.name = vat1.description = 'VAT1'
            vat1.type = 'percentage'
            vat1.rate = Decimal('0.2')
            vat1.invoice_account = tax_account
            vat1.credit_note_account = tax_account
            vat1.sequence = 20
            vat1.save()

            self.assertEqual(
                Tax.compute([ecotax1, vat1], Decimal(100), 5),
                [{
                        'base': Decimal(500),
                        'amount': Decimal(25),
                        'tax': ecotax1,
                        }, {
                        'base': Decimal(525),
                        'amount': Decimal(105),
                        'tax': vat1,
                        }])
            self.assertEqual(
                Tax.reverse_compute(Decimal(126), [ecotax1, vat1]),
                Decimal(100))

            ecotax2 = Tax()
            ecotax2.name = ecotax2.description = 'EcoTax 2'
            ecotax2.type = 'percentage'
            ecotax2.rate = Decimal('0.5')
            ecotax2.invoice_account = tax_account
            ecotax2.credit_note_account = tax_account
            ecotax2.update_unit_price = True
            ecotax2.sequence = 10
            ecotax2.save()

            self.assertEqual(
                Tax.compute([ecotax1, ecotax2, vat1], Decimal(100), 1),
                [{
                        'base': Decimal(100),
                        'amount': Decimal(5),
                        'tax': ecotax1,
                        }, {
                        'base': Decimal(100),
                        'amount': Decimal(50),
                        'tax': ecotax2,
                        }, {
                        'base': Decimal(155),
                        'amount': Decimal(31),
                        'tax': vat1,
                        }])
            self.assertEqual(
                Tax.reverse_compute(Decimal(186),
                    [ecotax1, ecotax2, vat1]),
                Decimal(100))

            vat0 = Tax()
            vat0.name = vat0.description = 'VAT0'
            vat0.type = 'percentage'
            vat0.rate = Decimal('0.1')
            vat0.invoice_account = tax_account
            vat0.credit_note_account = tax_account
            vat0.sequence = 5
            vat0.save()

            self.assertEqual(
                Tax.compute([vat0, ecotax1, vat1], Decimal(100), 1),
                [{
                        'base': Decimal(100),
                        'amount': Decimal(10),
                        'tax': vat0,
                        }, {
                        'base': Decimal(100),
                        'amount': Decimal(5),
                        'tax': ecotax1,
                        }, {
                        'base': Decimal(105),
                        'amount': Decimal(21),
                        'tax': vat1,
                        }])
            self.assertEqual(
                Tax.reverse_compute(Decimal(136),
                    [vat0, ecotax1, vat1]),
                Decimal(100))

            self.assertEqual(
                Tax.compute([vat0, ecotax1, ecotax2, vat1],
                    Decimal(100), 1),
                [{
                        'base': Decimal(100),
                        'amount': Decimal(10),
                        'tax': vat0,
                        }, {
                        'base': Decimal(100),
                        'amount': Decimal(5),
                        'tax': ecotax1,
                        }, {
                        'base': Decimal(100),
                        'amount': Decimal(50),
                        'tax': ecotax2,
                        }, {
                        'base': Decimal(155),
                        'amount': Decimal(31),
                        'tax': vat1,
                        }])
            self.assertEqual(
                Tax.reverse_compute(Decimal(196),
                    [vat0, ecotax1, ecotax2, vat1]),
                Decimal(100))

            vat2 = Tax()
            vat2.name = vat2.description = 'VAT2'
            vat2.type = 'percentage'
            vat2.rate = Decimal('0.3')
            vat2.invoice_account = tax_account
            vat2.credit_note_account = tax_account
            vat2.sequence = 30
            vat2.save()

            self.assertEqual(
                Tax.compute([vat0, ecotax1, vat1, vat2],
                    Decimal(100), 1),
                [{
                        'base': Decimal(100),
                        'amount': Decimal(10),
                        'tax': vat0,
                        }, {
                        'base': Decimal(100),
                        'amount': Decimal(5),
                        'tax': ecotax1,
                        }, {
                        'base': Decimal(105),
                        'amount': Decimal(21),
                        'tax': vat1,
                        }, {
                        'base': Decimal(105),
                        'amount': Decimal('31.5'),
                        'tax': vat2,
                        }])
            self.assertEqual(
                Tax.reverse_compute(Decimal('167.5'),
                    [vat0, ecotax1, vat1, vat2]),
                Decimal(100))

            ecotax3 = Tax()
            ecotax3.name = ecotax3.description = 'ECOTAX3'
            ecotax3.type = 'percentage'
            ecotax3.rate = Decimal('0.4')
            ecotax3.invoice_account = tax_account
            ecotax3.credit_note_account = tax_account
            ecotax3.update_unit_price = True
            ecotax3.sequence = 25
            ecotax3.save()

            self.assertEqual(
                Tax.compute([vat0, ecotax1, vat1, ecotax3, vat2],
                    Decimal(100), 1),
                [{
                        'base': Decimal(100),
                        'amount': Decimal(10),
                        'tax': vat0,
                        }, {
                        'base': Decimal(100),
                        'amount': Decimal(5),
                        'tax': ecotax1,
                        }, {
                        'base': Decimal(105),
                        'amount': Decimal(21),
                        'tax': vat1,
                        }, {
                        'base': Decimal(105),
                        'amount': Decimal('42'),
                        'tax': ecotax3,
                        }, {
                        'base': Decimal(147),
                        'amount': Decimal('44.1'),
                        'tax': vat2
                        }])
            self.assertEqual(
                Tax.reverse_compute(Decimal('222.1'),
                    [vat0, ecotax1, vat1, ecotax3, vat2]),
                Decimal(100))

    class Taxable(TaxableMixin):
        __slots__ = ('currency', 'taxable_lines')

        def __init__(self, currency=None, taxable_lines=None):
            super().__init__()
            self.currency = currency
            self.taxable_lines = taxable_lines

    @with_transaction()
    def test_taxable_mixin_line(self):
        "Test TaxableMixin with rounding on line"
        pool = Pool()
        Tax = pool.get('account.tax')
        Configuration = pool.get('account.configuration')
        currency = create_currency('cur')

        company = create_company()
        with set_company(company):
            create_chart(company, tax=True)
            tax, = Tax.search([])
            config = Configuration(1)
            config.tax_rounding = 'line'
            config.save()

            taxable = self.Taxable(
                currency=currency,
                taxable_lines=[
                    ([tax], Decimal('1.001'), 1, None),
                    ] * 100)

            taxes = taxable._get_taxes()

        tax, = taxes
        self.assertEqual(tax['base'], Decimal('100.00'))
        self.assertEqual(tax['amount'], Decimal('20.00'))

    @with_transaction()
    def test_taxable_mixin_document(self):
        "Test TaxableMixin with rounding on document"
        pool = Pool()
        Tax = pool.get('account.tax')
        Configuration = pool.get('account.configuration')
        currency = create_currency('cur')

        class Taxable(TaxableMixin):
            __slots__ = ('currency', 'taxable_lines')

            def __init__(self, currency=None, taxable_lines=None):
                super().__init__()
                self.currency = currency
                self.taxable_lines = taxable_lines

        company = create_company()
        with set_company(company):
            create_chart(company, tax=True)
            tax, = Tax.search([])
            config = Configuration(1)
            config.tax_rounding = 'document'
            config.save()

            taxable = Taxable(
                currency=currency,
                taxable_lines=[
                    ([tax], Decimal('1.001'), 1, None),
                    ] * 100)

            taxes = taxable._get_taxes()

        tax, = taxes
        self.assertEqual(tax['base'], Decimal('100.00'))
        self.assertEqual(tax['amount'], Decimal('20.02'))

    @with_transaction()
    def test_tax_compute_with_children_update_unit_price(self):
        "Test tax compute with children taxes modifying unit_price"
        pool = Pool()
        Account = pool.get('account.account')
        Tax = pool.get('account.tax')

        company = create_company()
        with set_company(company):
            create_chart(company)

            tax_account, = Account.search([
                    ('name', '=', 'Main Tax'),
                    ])

            tax1 = Tax()
            tax1.name = tax1.description = "Tax 1"
            tax1.type = 'none'
            tax1.update_unit_price = True
            tax1.sequence = 1
            tax1.save()
            child1 = Tax()
            child1.name = child1.description = "Child 1"
            child1.type = 'percentage'
            child1.rate = Decimal('0.1')
            child1.invoice_account = tax_account
            child1.credit_note_account = tax_account
            child1.parent = tax1
            child1.save()

            tax2 = Tax()
            tax2.name = tax2.description = "Tax 2"
            tax2.type = 'fixed'
            tax2.amount = Decimal('10')
            tax2.invoice_account = tax_account
            tax2.credit_note_account = tax_account
            tax2.sequence = 2
            tax2.save()

            self.assertEqual(
                Tax.compute([tax1, tax2], Decimal(100), 2), [{
                        'base': Decimal(200),
                        'amount': Decimal(20),
                        'tax': child1,
                        }, {
                        'base': Decimal('220'),
                        'amount': Decimal('20'),
                        'tax': tax2,
                        }])
            self.assertEqual(
                Tax.reverse_compute(Decimal('120'), [tax1, tax2]),
                Decimal('100'))

    @with_transaction()
    def test_receivable_payable(self):
        'Test party receivable payable'
        pool = Pool()
        Party = pool.get('party.party')
        FiscalYear = pool.get('account.fiscalyear')
        Journal = pool.get('account.journal')
        Account = pool.get('account.account')
        Move = pool.get('account.move')

        company = create_company()
        with set_company(company):
            create_chart(company)
            fiscalyear = get_fiscalyear(company)
            fiscalyear.save()
            FiscalYear.create_period([fiscalyear])
            period = fiscalyear.periods[0]
            journal_revenue, = Journal.search([
                    ('code', '=', 'REV'),
                    ])
            journal_expense, = Journal.search([
                    ('code', '=', 'EXP'),
                    ])
            revenue, = Account.search([
                    ('type.revenue', '=', True),
                    ])
            receivable, = Account.search([
                    ('type.receivable', '=', True),
                    ])
            expense, = Account.search([
                    ('type.expense', '=', True),
                    ])
            payable, = Account.search([
                    ('type.payable', '=', True),
                    ])
            party, = Party.create([{
                        'name': 'Receivable/Payable party',
                        }])
            tomorrow = datetime.date.today() + datetime.timedelta(days=1)

            def get_move(journal, amount, credit_account, debit_account, party,
                    maturity_date=None):
                return {
                    'period': period.id,
                    'journal': journal.id,
                    'date': period.start_date,
                    'lines': [
                        ('create', [{
                                    'account': credit_account.id,
                                    'credit': amount,
                                    }, {
                                    'account': debit_account.id,
                                    'debit': amount,
                                    'party': party.id,
                                    'maturity_date': maturity_date,
                                    }]),
                        ],
                    }
            vlist = [
                get_move(journal_revenue, Decimal(100), revenue, receivable,
                    party),
                get_move(journal_expense, Decimal(30), expense, payable,
                    party),
                get_move(journal_revenue, Decimal(200), revenue, receivable,
                    party, tomorrow),
                get_move(journal_revenue, Decimal(60), expense, payable,
                    party, tomorrow),
                ]
            moves = Move.create(vlist)
            Move.post(moves)

            def check_fields():
                party_test = Party(party.id)

                for field, value in [('receivable', Decimal('300')),
                        ('receivable_today', Decimal('100')),
                        ('payable', Decimal('90')),
                        ('payable_today', Decimal('30')),
                        ]:
                    msg = 'field: %s, value: %s' % (field, value)
                    self.assertEqual(
                        getattr(party_test, field), value, msg=msg)
                    self.assertEqual(
                        Party.search([(field, '=', value)]),
                        [party_test], msg=msg)
                    self.assertEqual(
                        Party.search([(field, 'in', [value])]),
                        [party_test], msg=msg)
                    self.assertEqual(
                        Party.search([(field, '!=', value)]),
                        [], msg=msg)
                    self.assertEqual(
                        Party.search([(field, 'not in', [value])]),
                        [], msg=msg)

            check_fields()
            close_fiscalyear(fiscalyear)
            check_fields()

    @with_transaction()
    def test_sort_taxes(self):
        "Test sort_taxes"
        pool = Pool()
        Tax = pool.get('account.tax')

        tax1 = Tax(sequence=None, id=-3)
        tax2 = Tax(sequence=None, id=-2)
        tax3 = Tax(sequence=1, id=-1)
        self.assertSequenceEqual(
            Tax.sort_taxes([tax3, tax2, tax1]), [tax1, tax2, tax3])

    @with_transaction()
    def test_configuration_accounts_on_party(self):
        'Test configuration accounts are used as fallback on party'
        pool = Pool()
        Party = pool.get('party.party')
        Account = pool.get('account.account')

        party = Party(name='Party')
        party.save()

        self.assertIsNone(party.account_payable)
        self.assertIsNone(party.account_receivable)

        company = create_company()
        with set_company(company):
            create_chart(company)
            receivable, = Account.search([
                    ('type.receivable', '=', True),
                    ])
            payable, = Account.search([
                    ('type.payable', '=', True),
                    ])

            party = Party(party.id)

            self.assertEqual(party.account_payable_used, payable)
            self.assertEqual(party.account_receivable_used, receivable)

    @with_transaction()
    def test_tax_rule(self):
        "Test tax rule"
        pool = Pool()
        TaxRule = pool.get('account.tax.rule')
        Tax = pool.get('account.tax')

        company = create_company()
        with set_company(company):
            create_chart(company, tax=True)
            tax, = Tax.search([])
            target_tax, = Tax.copy([tax])

            tax_rule, = TaxRule.create([{
                        'name': 'Test',
                        'kind': 'both',
                        'lines': [('create', [{
                                        'origin_tax': tax.id,
                                        'tax': target_tax.id,
                                        }])],
                        }])
            self.assertListEqual(tax_rule.apply(tax, {}), [target_tax.id])

    @with_transaction()
    def test_tax_rule_start_date(self):
        "Test tax rule start date"
        pool = Pool()
        TaxRule = pool.get('account.tax.rule')
        Tax = pool.get('account.tax')
        Date = pool.get('ir.date')

        today = Date.today()
        yesterday = today - datetime.timedelta(days=1)
        tomorrow = today + datetime.timedelta(days=1)
        company = create_company()
        with set_company(company):
            create_chart(company, tax=True)
            tax, = Tax.search([])
            target_tax, = Tax.copy([tax])

            tax_rule, = TaxRule.create([{
                        'name': "Test",
                        'kind': 'both',
                        'lines': [('create', [{
                                        'start_date': today,
                                        'tax': target_tax.id,
                                        }])],
                        }])

            self.assertListEqual(tax_rule.apply(tax, {}), [target_tax.id])
            self.assertListEqual(
                tax_rule.apply(tax, {'date': yesterday}), [tax.id])
            self.assertListEqual(
                tax_rule.apply(tax, {'date': tomorrow}), [target_tax.id])

    @with_transaction()
    def test_tax_rule_end_date(self):
        "Test tax rule end date"
        pool = Pool()
        TaxRule = pool.get('account.tax.rule')
        Tax = pool.get('account.tax')
        Date = pool.get('ir.date')

        today = Date.today()
        yesterday = today - datetime.timedelta(days=1)
        tomorrow = today + datetime.timedelta(days=1)
        company = create_company()
        with set_company(company):
            create_chart(company, tax=True)
            tax, = Tax.search([])
            target_tax, = Tax.copy([tax])

            tax_rule, = TaxRule.create([{
                        'name': "Test",
                        'kind': 'both',
                        'lines': [('create', [{
                                        'end_date': today,
                                        'tax': target_tax.id,
                                        }])],
                        }])

            self.assertListEqual(tax_rule.apply(tax, {}), [target_tax.id])
            self.assertListEqual(
                tax_rule.apply(tax, {'date': yesterday}), [target_tax.id])
            self.assertListEqual(
                tax_rule.apply(tax, {'date': tomorrow}), [tax.id])

    @with_transaction()
    def test_tax_rule_keep_origin(self):
        "Test tax rule keeps origin"
        pool = Pool()
        TaxRule = pool.get('account.tax.rule')
        Tax = pool.get('account.tax')

        company = create_company()
        with set_company(company):
            create_chart(company, tax=True)
            tax, = Tax.search([])
            target_tax, = Tax.copy([tax])

            tax_rule, = TaxRule.create([{
                        'name': 'Test',
                        'kind': 'both',
                        'lines': [('create', [{
                                        'origin_tax': tax.id,
                                        'tax': target_tax.id,
                                        'keep_origin': True,
                                        }])],
                        }])
            self.assertListEqual(
                tax_rule.apply(tax, {}), [target_tax.id, tax.id])

    @with_transaction()
    def test_update_chart(self):
        'Test all template models are updated when updating chart'
        pool = Pool()
        TypeTemplate = pool.get('account.account.type.template')
        AccountTemplate = pool.get('account.account.template')
        TaxTemplate = pool.get('account.tax.template')
        TaxCodeTemplate = pool.get('account.tax.code.template')
        ModelData = pool.get('ir.model.data')
        UpdateChart = pool.get('account.update_chart', type='wizard')
        Type = pool.get('account.account.type')
        Account = pool.get('account.account')
        Tax = pool.get('account.tax')
        TaxCode = pool.get('account.tax.code')

        def check():
            for type_ in Type.search([]):
                self.assertEqual(type_.name, type_.template.name)
                self.assertEqual(
                    type_.statement, type_.template.statement)

            for account in Account.search([]):
                self.assertEqual(account.name, account.template.name)
                self.assertEqual(account.code, account.template.code)
                self.assertEqual(account.type.template, account.template.type)
                self.assertEqual(account.reconcile, account.template.reconcile)
                self.assertEqual(
                    account.start_date, account.template.start_date)
                self.assertEqual(account.end_date, account.template.end_date)
                self.assertEqual(
                    account.party_required, account.template.party_required)
                self.assertEqual(
                    account.general_ledger_balance,
                    account.template.general_ledger_balance)
                self.assertEqual(
                    set(t.template for t in account.taxes),
                    set(t for t in account.template.taxes))

            for tax_code in TaxCode.search([]):
                self.assertEqual(tax_code.name, tax_code.template.name)
                self.assertEqual(tax_code.code, tax_code.template.code)
                for line in tax_code.lines:
                    self.assertEqual(line.code.template, line.template.code)
                    self.assertEqual(line.operator, line.template.operator)
                    self.assertEqual(line.type, line.template.type)
                    self.assertEqual(line.tax.template, line.template.tax)

            for tax in Tax.search([]):
                self.assertEqual(tax.name, tax.template.name)
                self.assertEqual(tax.description, tax.template.description)
                self.assertEqual(tax.type, tax.template.type)
                self.assertEqual(tax.rate, tax.template.rate)
                self.assertEqual(tax.amount, tax.template.amount)
                self.assertEqual(
                    tax.update_unit_price, tax.template.update_unit_price)
                self.assertEqual(
                    tax.start_date, tax.template.start_date)
                self.assertEqual(tax.end_date, tax.template.end_date)
                self.assertEqual(
                    tax.invoice_account.template, tax.template.invoice_account)
                self.assertEqual(
                    tax.credit_note_account.template,
                    tax.template.credit_note_account)

        company = create_company()
        with set_company(company):
            create_chart(company, True)

            with Transaction().set_context(active_test=False):
                self.assertEqual(Type.search([], count=True), 16)
                self.assertEqual(Account.search([], count=True), 7)
                self.assertEqual(Tax.search([], count=True), 1)

                check()

        with Transaction().set_user(0):
            root_type = TypeTemplate(ModelData.get_id(
                'account', 'account_type_template_minimal_en'))
            root_type.name = 'Updated Minimal Chart'
            root_type.save()
            chart = AccountTemplate(ModelData.get_id(
                    'account', 'account_template_root_en'))
            new_type = TypeTemplate()
            new_type.name = 'New Type'
            new_type.parent = root_type
            new_type.statement = 'balance'
            new_type.save()
            new_account = AccountTemplate()
            new_account.name = 'New Account'
            new_account.parent = chart
            new_account.type = new_type
            new_account.save()
            updated_tax, = TaxTemplate.search([])
            updated_tax.name = 'VAT'
            updated_tax.invoice_account = new_account
            updated_tax.save()
            updated_account = AccountTemplate(ModelData.get_id(
                    'account', 'account_template_revenue_en'))
            updated_account.code = 'REV'
            updated_account.name = 'Updated Account'
            updated_account.reconcile = True
            updated_account.end_date = datetime.date.today()
            updated_account.taxes = [updated_tax]
            updated_account.save()
            inactive_account = AccountTemplate(ModelData.get_id(
                    'account', 'account_template_expense_en'))
            inactive_account.end_date = datetime.date.min
            inactive_account.save()
            new_tax = TaxTemplate()
            new_tax.name = new_tax.description = '10% VAT'
            new_tax.type = 'percentage'
            new_tax.rate = Decimal('0.1')
            new_tax.account = chart
            new_tax.invoice_account = new_account
            new_tax.credit_note_account = new_account
            new_tax.save()
            updated_tax_code, = TaxCodeTemplate.search([
                    ('name', '=', 'Tax Code'),
                    ])
            updated_tax_code.name = 'Updated Tax Code'
            updated_tax_code.save()
            updated_tax_code_line, = updated_tax_code.lines
            updated_tax_code_line.operator = '-'
            updated_tax_code_line.save()

        with set_company(company):
            account, = Account.search([('parent', '=', None)])
            session_id, _, _ = UpdateChart.create()
            update_chart = UpdateChart(session_id)
            update_chart.start.account = account
            update_chart.transition_update()

            with Transaction().set_context(active_test=False):
                self.assertEqual(Type.search([], count=True), 17)
                self.assertEqual(Account.search([], count=True), 8)
                self.assertEqual(Tax.search([], count=True), 2)

                check()

    @with_transaction()
    def test_update_override(self):
        "Test all models are not updated when template override is True"
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        TypeTemplate = pool.get('account.account.type.template')
        AccountTemplate = pool.get('account.account.template')
        TaxTemplate = pool.get('account.tax.template')
        TaxCodeTemplate = pool.get('account.tax.code.template')
        UpdateChart = pool.get('account.update_chart', type='wizard')
        Type = pool.get('account.account.type')
        Account = pool.get('account.account')
        Tax = pool.get('account.tax')
        TaxCode = pool.get('account.tax.code')
        TaxCodeLine = pool.get('account.tax.code.line')

        new_name = "Updated"

        company = create_company()
        with set_company(company):
            create_chart(company, True)

            type_count = Type.search([], count=True)
            account_count = Account.search([], count=True)
            tax_count = Tax.search([], count=True)
            tax_code_count = TaxCode.search([], count=True)
            tax_code_line_count = TaxCodeLine.search([], count=True)

        with Transaction().set_user(0):
            root = AccountTemplate(ModelData.get_id(
                    'account', 'account_template_root_en'))

            template_type, = TypeTemplate.search([
                    ('parent', '!=', None),
                    ('parent', 'child_of', [root.type.id]),
                    ], limit=1)
            template_type.name = new_name
            template_type.save()
            type_, = Type.search([('template', '=', template_type.id)])
            type_.template_override = True
            type_.save()

            template_account, = AccountTemplate.search([
                    ('parent', '!=', None),
                    ('parent', 'child_of', [root.id]),
                    ], limit=1)
            template_account.name = new_name
            template_account.save()
            account, = Account.search([('template', '=', template_account.id)])
            account.template_override = True
            account.save()

            template_tax, = TaxTemplate.search([])
            template_tax.name = new_name
            template_tax.save()
            tax, = Tax.search([('template', '=', template_tax.id)])
            tax.template_override = True
            tax.save()

            template_tax_code, = TaxCodeTemplate.search([], limit=1)
            template_tax_code.name = new_name
            template_tax_code.save()
            tax_code, = TaxCode.search(
                [('template', '=', template_tax_code.id)])
            tax_code.template_override = True
            tax_code.save()

            template_tax_code_line, = TaxCodeLine.search([], limit=1)
            tax_code_line, = TaxCodeLine.search(
                [('template', '=', template_tax_code_line.id)])
            tax_code_line.template_override = True
            tax_code_line.save()

        with set_company(company):
            account, = Account.search([('parent', '=', None)])
            session_id, _, _ = UpdateChart.create()
            update_chart = UpdateChart(session_id)
            update_chart.start.account = account
            update_chart.transition_update()

            self.assertEqual(Type.search([], count=True), type_count)
            self.assertEqual(Account.search([], count=True), account_count)
            self.assertEqual(Tax.search([], count=True), tax_count)
            self.assertEqual(
                TaxCode.search([], count=True), tax_code_count)
            self.assertEqual(
                TaxCodeLine.search([], count=True), tax_code_line_count)

            for Model in [Type, Account, Tax, TaxCode]:
                for record in Model.search([]):
                    self.assertNotEqual(record.name, new_name)

    @with_transaction()
    def test_update_inactive(self):
        "Test update chart of accounts with inactive account"
        pool = Pool()
        Account = pool.get('account.account')
        UpdateChart = pool.get('account.update_chart', type='wizard')

        company = create_company()
        with set_company(company):
            create_chart(company, tax=True)
            root, = Account.search([('parent', '=', None)])

            cash, = Account.search([('name', '=', 'Main Cash')])
            cash.template_override = True
            cash.end_date = datetime.date.min
            cash.save()
            self.assertFalse(cash.active)

            session_id, _, _ = UpdateChart.create()
            update_chart = UpdateChart(session_id)
            update_chart.start.account = root
            update_chart.transition_update()

            with Transaction().set_context(active_test=False):
                self.assertEqual(
                    Account.search([('name', '=', 'Main Cash')], count=True),
                    1)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        AccountTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_account_reconciliation.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_account_reconcile.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_move_cancel.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_move_line_group.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_move_template.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_reports.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_renew_fiscalyear.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_account_active.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_tax_code.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
