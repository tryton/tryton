# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.i18n import gettext
from trytond.model import ModelSQL, ModelView, Unique, Workflow, fields
from trytond.model.exceptions import AccessError
from trytond.modules.account.exceptions import AccountMissing
from trytond.modules.currency.fields import Monetary
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If
from trytond.transaction import Transaction
from trytond.wizard import StateTransition, Wizard


class Configuration(metaclass=PoolMeta):
    __name__ = 'account.configuration'

    deferred_account_revenue = fields.MultiValue(fields.Many2One(
            'account.account', "Deferred Account Revenue",
            domain=[
                ('type.statement', '=', 'balance'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ]))
    deferred_account_expense = fields.MultiValue(fields.Many2One(
            'account.account', "Deferred Account Expense",
            domain=[
                ('type.statement', '=', 'balance'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ]))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {'deferred_account_revenue', 'deferred_account_expense'}:
            return pool.get('account.configuration.default_account')
        return super().multivalue_model(field)


class ConfigurationDefaultAccount(metaclass=PoolMeta):
    __name__ = 'account.configuration.default_account'

    deferred_account_revenue = fields.Many2One(
        'account.account', "Deferred Account Revenue",
        domain=[
            ('type.statement', '=', 'balance'),
            ('company', '=', Eval('company', -1)),
            ])
    deferred_account_expense = fields.Many2One(
        'account.account', "Deferred Account Expense",
        domain=[
            ('type.statement', '=', 'balance'),
            ('company', '=', Eval('company', -1)),
            ])


class InvoiceDeferred(Workflow, ModelSQL, ModelView):
    "Invoice Deferred"
    __name__ = 'account.invoice.deferred'

    _states = {
        'readonly': Eval('state') != 'draft',
        }

    company = fields.Many2One(
        'company.company', "Company", required=True,
        states={
            'readonly': (Eval('state') != 'draft') & Eval('invoice_line'),
            })
    type = fields.Selection([
            ('out', "Customer"),
            ('in', "Supplier"),
            ], "Type", required=True,
        states=_states)
    journal = fields.Many2One(
        'account.journal', "Journal", required=True,
        states=_states,
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    invoice_line = fields.Many2One(
        'account.invoice.line', "Invoice Line", required=True,
        domain=[
            ('product.type', '=', 'service'),
            ('invoice.type', '=', Eval('type')),
            ('invoice.state', 'in', ['posted', 'paid']),
            ('invoice.company', '=', Eval('company', -1)),
            ],
        states=_states)
    amount = Monetary(
        "Amount", currency='currency', digits='currency', required=True,
        states=_states)
    start_date = fields.Date(
        "Start Date", required=True,
        domain=[
            ('start_date', '<', Eval('end_date', None)),
            ],
        states=_states)
    end_date = fields.Date(
        "End Date", required=True,
        domain=[
            ('end_date', '>', Eval('start_date', None)),
            ],
        states=_states)
    moves = fields.One2Many(
        'account.move', 'origin', "Moves", readonly=True,
        order=[
            ('period.start_date', 'ASC'),
            ])
    state = fields.Selection([
            ('draft', "Draft"),
            ('running', "Running"),
            ('closed', "Closed"),
            ], "State", readonly=True, required=True, sort=False)

    currency = fields.Function(fields.Many2One(
            'currency.currency', "Currency"), 'on_change_with_currency')

    del _states

    @classmethod
    def __setup__(cls):
        super().__setup__()
        table = cls.__table__()
        cls._sql_constraints = [
            ('invoice_line_unique', Unique(table, table.invoice_line),
                'account_invoice_defer.msg_defer_invoice_line_unique'),
            ]
        cls.journal.domain = [
            If(Eval('type') == 'out',
                ('type', 'in', cls._journal_types('out')),
                ('type', 'in', cls._journal_types('in'))),
            ]
        cls._transitions |= set((
                ('draft', 'running'),
                ('running', 'closed'),
                ))
        cls._buttons.update({
                'run': {
                    'invisible': Eval('state') != 'draft',
                    'depends': ['state'],
                    },
                })

    @classmethod
    def _journal_types(cls, type):
        if type == 'out':
            return ['revenue']
        else:
            return ['expense']

    @fields.depends('type')
    def on_change_type(self):
        Journal = self.__class__.journal.get_target()
        journal_types = self.__class__._journal_types(self.type)
        journals = Journal.search([
                ('type', 'in', journal_types),
                ], limit=1)
        if journals:
            self.journal, = journals

    @fields.depends('invoice_line', 'start_date', 'company')
    def on_change_invoice_line(self):
        pool = Pool()
        Currency = pool.get('currency.currency')
        if self.invoice_line:
            if not self.start_date:
                self.start_date = self.invoice_line.invoice.invoice_date
            invoice = self.invoice_line.invoice
            if self.company and invoice.currency != self.company.currency:
                with Transaction().set_context(date=invoice.currency_date):
                    self.amount = Currency.compute(
                        invoice.currency, self.invoice_line.amount,
                        self.company.currency)
            else:
                self.amount = self.invoice_line.amount

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_state(cls):
        return 'draft'

    @fields.depends('company')
    def on_change_with_currency(self, name=None):
        if self.company:
            return self.company.currency.id

    @classmethod
    @ModelView.button
    @Workflow.transition('running')
    def run(cls, deferrals):
        pool = Pool()
        Period = pool.get('account.period')
        # Ensure it starts at an opened period
        for deferral in deferrals:
            Period.find(deferral.company.id, deferral.start_date)
        # Set state before create moves and defer amount to pass assert
        cls.write(deferrals, {'state': 'running'})
        cls.create_moves(deferrals)
        # defer_amount is called after create_moves to be sure that
        # create_moves call get_move with the invoice period if needed.
        cls.defer_amount(deferrals)
        cls.close_try(deferrals)

    @classmethod
    def close_try(cls, deferrals):
        "Try to close the deferrals if last move has been created"
        to_close = []
        for deferral in deferrals:
            if deferral.moves:
                last_move = deferral.moves[-1]
                if last_move.period.end_date >= deferral.end_date:
                    to_close.append(deferral)
        cls.close(to_close)

    @classmethod
    @Workflow.transition('closed')
    def close(cls, deferrals):
        for deferral in deferrals:
            assert (deferral.moves
                and deferral.moves[-1].period.end_date >= deferral.end_date)

    @classmethod
    def delete(cls, deferrals):
        for deferral in deferrals:
            if deferral.state != 'draft':
                raise AccessError(
                    gettext('account_invoice_defer'
                        '.msg_invoice_deferred_delete_draft',
                        deferral=deferral.rec_name))
        return super().delete(deferrals)

    @classmethod
    def defer_amount(cls, deferrals):
        pool = Pool()
        Move = pool.get('account.move')
        moves = []
        for deferral in deferrals:
            assert deferral.state == 'running'
            moves.append(deferral.get_move())
        Move.save(moves)
        Move.post(moves)

    @classmethod
    def create_moves(cls, deferrals):
        pool = Pool()
        Period = pool.get('account.period')
        Move = pool.get('account.move')
        moves = []
        for deferral in deferrals:
            assert deferral.state == 'running'
            periods = Period.search([
                    ('company', '=', deferral.company.id),
                    ('type', '=', 'standard'),
                    ('start_date', '<=', deferral.end_date),
                    ('end_date', '>=', deferral.start_date),
                    ])
            for period in sorted(
                    set(periods) - {m.period for m in deferral.moves},
                    key=lambda p: p.start_date):
                moves.append(deferral.get_move(period))
        Move.save(moves)
        to_save = []
        for deferral in deferrals:
            if deferral.moves:
                last_move = deferral.moves[-1]
                if last_move.period.end_date >= deferral.end_date:
                    remainder = deferral.amount_remainder
                    if remainder > 0:
                        for line in last_move.lines:
                            if line.debit:
                                line.debit += remainder
                            else:
                                line.credit += remainder
                    elif remainder < 0:
                        for line in last_move.lines:
                            if line.debit:
                                line.debit -= remainder
                            else:
                                line.credit -= remainder
                    if remainder:
                        to_save.append(last_move)
        Move.save(to_save)
        Move.post(moves)

    @property
    def amount_daily(self):
        days = (self.end_date - self.start_date).days + 1
        return self.amount / days

    @property
    def amount_remainder(self):
        period = self.invoice_line.invoice.move.period
        return abs(self.amount) - sum(
            l.credit for m in self.moves for l in m.lines
            if m.period != period)

    def get_move(self, period=None):
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Configuration = pool.get('account.configuration')
        configuration = Configuration(1)
        move = Move(
            company=self.company,
            origin=self,
            journal=self.journal,
            )
        invoice = self.invoice_line.invoice

        income = Line()
        if period is None:
            move.period = invoice.move.period
            move.date = invoice.move.date
            amount = self.amount
            if amount >= 0:
                if invoice.type == 'out':
                    income.debit, income.credit = amount, 0
                else:
                    income.debit, income.credit = 0, amount
            else:
                if invoice.type == 'out':
                    income.debit, income.credit = 0, -amount
                else:
                    income.debit, income.credit = -amount, 0
        else:
            move.period = period
            move.date = period.start_date
            days = (
                min(period.end_date, self.end_date)
                - max(period.start_date, self.start_date)).days + 1
            amount = self.company.currency.round(self.amount_daily * days)
            if amount >= 0:
                if invoice.type == 'out':
                    income.debit, income.credit = 0, amount
                else:
                    income.debit, income.credit = amount, 0
            else:
                if invoice.type == 'out':
                    income.debit, income.credit = -amount, 0
                else:
                    income.debit, income.credit = 0, -amount
        income.account = self.invoice_line.account.current(move.date)
        if income.account.party_required:
            income.party = invoice.party

        balance = Line()
        if invoice.type == 'out':
            balance.account = configuration.get_multivalue(
                'deferred_account_revenue', company=self.company.id)
            if not balance.account:
                raise AccountMissing(gettext(
                        'account_invoice_defer.'
                        'msg_missing_deferred_account_revenue'))
        else:
            balance.account = configuration.get_multivalue(
                'deferred_account_expense', company=self.company.id)
            if not balance.account:
                raise AccountMissing(gettext(
                        'account_invoice_defer.'
                        'msg_missing_deferred_account_expense'))
        balance.debit, balance.credit = income.credit, income.debit
        if balance.account.party_required:
            balance.party = invoice.party

        move.lines = [balance, income]
        return move


class InvoiceDeferredCreateMoves(Wizard):
    "Invoice Deferred Create Moves"
    __name__ = 'account.invoice.deferred.create_moves'
    start_state = 'create_moves'
    create_moves = StateTransition()

    def transition_create_moves(self):
        pool = Pool()
        InvoiceDeferred = pool.get('account.invoice.deferred')
        with Transaction().set_context(_check_access=True):
            deferrals = InvoiceDeferred.search([
                    ('state', '=', 'running'),
                    ])
        deferrals = InvoiceDeferred.browse(deferrals)
        InvoiceDeferred.create_moves(deferrals)
        InvoiceDeferred.close_try(deferrals)
        return 'end'


class Move(metaclass=PoolMeta):
    __name__ = 'account.move'

    @classmethod
    def _get_origin(cls):
        return super()._get_origin() + ['account.invoice.deferred']


class Period(metaclass=PoolMeta):
    __name__ = 'account.period'

    @classmethod
    def close(cls, periods):
        for period in periods:
            period.check_invoice_deferred_running()
        super().close(periods)

    def check_invoice_deferred_running(self):
        """
        Check if it exists any invoice deferred
        without account move for the period.
        """
        pool = Pool()
        InvoiceDeferred = pool.get('account.invoice.deferred')
        deferrals = InvoiceDeferred.search([
                ('state', '=', 'running'),
                ('company', '=', self.company.id),
                ['OR', [
                        ('start_date', '<=', self.start_date),
                        ('end_date', '>=', self.start_date),
                        ], [
                        ('start_date', '<=', self.end_date),
                        ('end_date', '>=', self.end_date),
                        ], [
                        ('start_date', '>=', self.start_date),
                        ('end_date', '<=', self.end_date),
                        ],
                    ],
                ('moves', 'not where', [
                        ('date', '>=', self.start_date),
                        ('date', '<=', self.end_date),
                        ]),
                ], limit=6)
        if deferrals:
            names = ', '.join(d.rec_name for d in deferrals[:5])
            if len(deferrals) > 5:
                names += '...'
            raise AccessError(
                gettext('account_invoice_defer'
                    '.msg_invoice_deferred_running_close_period',
                    period=self.rec_name,
                    deferrals=names))


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    @classmethod
    def _post(cls, invoices):
        pool = Pool()
        InvoiceDeferred = pool.get('account.invoice.deferred')
        super()._post(invoices)
        deferrals = []
        for invoice in invoices:
            for line in invoice.lines:
                if line.deferrable and line.defer_from and line.defer_to:
                    deferral = InvoiceDeferred(
                        company=invoice.company,
                        type=invoice.type,
                        journal=invoice.journal,
                        invoice_line=line,
                        start_date=line.defer_from,
                        end_date=line.defer_to)
                    deferral.on_change_invoice_line()
                    deferrals.append(deferral)
        InvoiceDeferred.save(deferrals)


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    deferrable = fields.Function(
        fields.Boolean("Deferrable"), 'on_change_with_deferrable')
    defer_from = fields.Date(
        "Defer From",
        domain=[
            If(Eval('deferrable', False) & Eval('defer_to', None),
                ('defer_from', '<', Eval('defer_to', None)),
                ()),
            ],
        states={
            'readonly': Eval('invoice_state') != 'draft',
            'invisible': ~Eval('deferrable', False),
            })
    defer_to = fields.Date(
        "Defer To",
        domain=[
            If(Eval('deferrable', False) & Eval('defer_from', None),
                ('defer_to', '>', Eval('defer_from', None)),
                ()),
            ],
        states={
            'readonly': Eval('invoice_state') != 'draft',
            'invisible': ~Eval('deferrable', False),
            })

    @fields.depends('product')
    def on_change_with_deferrable(self, name=None):
        if self.product:
            return self.product.type == 'service'
