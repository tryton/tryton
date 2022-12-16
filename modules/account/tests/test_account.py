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
from trytond.modules.currency.tests import create_currency


def create_chart(company, tax=False):
    pool = Pool()
    AccountTemplate = pool.get('account.account.template')
    TaxTemplate = pool.get('account.tax.template')
    TaxCodeTemplate = pool.get('account.tax.code.template')
    ModelData = pool.get('ir.model.data')
    CreateChart = pool.get('account.create_chart', type='wizard')
    Account = pool.get('account.account')

    template = AccountTemplate(ModelData.get_id(
            'account', 'account_template_root_en'))
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

            tax_code = TaxCodeTemplate()
            tax_code.name = 'Tax Code'
            tax_code.account = template
            tax_code.save()
            base_code = TaxCodeTemplate()
            base_code.name = 'Base Code'
            base_code.account = template
            base_code.save()

    session_id, _, _ = CreateChart.create()
    create_chart = CreateChart(session_id)
    create_chart.account.account_template = template
    create_chart.account.company = company
    create_chart.transition_create_account()
    receivable, = Account.search([
            ('kind', '=', 'receivable'),
            ('company', '=', company.id),
            ])
    payable, = Account.search([
            ('kind', '=', 'payable'),
            ('company', '=', company.id),
            ])
    create_chart.properties.company = company
    create_chart.properties.account_receivable = receivable
    create_chart.properties.account_payable = payable
    create_chart.transition_create_properties()


def get_fiscalyear(company, today=None):
    pool = Pool()
    Sequence = pool.get('ir.sequence')
    FiscalYear = pool.get('account.fiscalyear')

    if not today:
        today = datetime.date.today()

    sequence, = Sequence.create([{
                'name': '%s' % today.year,
                'code': 'account.move',
                'company': company.id,
                }])
    fiscalyear = FiscalYear(name='%s' % today.year, company=company)
    fiscalyear.start_date = today.replace(month=1, day=1)
    fiscalyear.end_date = today.replace(month=12, day=31)
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
            ('kind', '=', 'revenue'),
            ])
    account_pl, = Account.create([{
                'name': 'P&L',
                'type': type_equity.id,
                'deferral': True,
                'parent': revenue.parent.id,
                'kind': 'other',
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
            cash, = Account.search([
                    ('kind', '=', 'other'),
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
                    ('kind', '=', 'revenue'),
                    ])
            receivable, = Account.search([
                    ('kind', '=', 'receivable'),
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
                    ('kind', '=', 'receivable'),
                    ])
            payable, = Account.search([
                    ('kind', '=', 'payable'),
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
    return suite
