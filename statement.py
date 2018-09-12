# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from collections import namedtuple, defaultdict
from itertools import groupby

from sql import Null
from sql.conditionals import Coalesce
from sql.aggregate import Max, Sum

from trytond.config import config
from trytond.model import Workflow, ModelView, ModelSQL, fields, Check, \
    sequence_ordered, DictSchemaMixin
from trytond.pyson import Eval, If, Bool
from trytond.transaction import Transaction
from trytond import backend
from trytond.pool import Pool
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.modules.company import CompanyReport

__all__ = ['Statement', 'Line', 'LineGroup',
    'Origin', 'OriginInformation',
    'ImportStatementStart', 'ImportStatement',
    'ReconcileStatement',
    'StatementReport']

_STATES = {'readonly': Eval('state') != 'draft'}
_DEPENDS = ['state']

_BALANCE_STATES = _STATES.copy()
_BALANCE_STATES.update({
        'invisible': ~Eval('validation', '').in_(['balance']),
        'required': Eval('validation', '').in_(['balance']),
        })
_BALANCE_DEPENDS = _DEPENDS + ['validation']

_AMOUNT_STATES = _STATES.copy()
_AMOUNT_STATES.update({
        'invisible': ~Eval('validation', '').in_(['amount']),
        'required': Eval('validation', '').in_(['amount']),
        })
_AMOUNT_DEPENDS = _DEPENDS + ['validation']

_NUMBER_STATES = _STATES.copy()
_NUMBER_STATES.update({
        'invisible': ~Eval('validation', '').in_(['number_of_lines']),
        'required': Eval('validation', '').in_(['number_of_lines']),
        })
_NUMBER_DEPENDS = _DEPENDS + ['validation']

STATES = [
    ('draft', 'Draft'),
    ('validated', 'Validated'),
    ('cancel', 'Canceled'),
    ('posted', 'Posted'),
    ]

if config.getboolean('account_statement', 'filestore', default=False):
    file_id = 'origin_file_id'
    store_prefix = config.get(
        'account_statement', 'store_prefix', default=None)
else:
    file_id = None
    store_prefix = None


class Unequal(object):
    "Always different"

    def __eq__(self, other):
        return False

    def __ne__(self, other):
        return True

    def __str__(self):
        return ''


class Statement(Workflow, ModelSQL, ModelView):
    'Account Statement'
    __name__ = 'account.statement'
    name = fields.Char('Name', required=True)
    company = fields.Many2One('company.company', 'Company', required=True,
        select=True, states=_STATES, domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
        depends=_DEPENDS)
    journal = fields.Many2One('account.statement.journal', 'Journal',
        required=True, select=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        states={
            'readonly': (Eval('state') != 'draft') | Eval('lines', [0]),
            },
        depends=['state', 'company'])
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    date = fields.Date('Date', required=True, select=True)
    start_balance = fields.Numeric('Start Balance',
        digits=(16, Eval('currency_digits', 2)),
        states=_BALANCE_STATES, depends=_BALANCE_DEPENDS + ['currency_digits'])
    end_balance = fields.Numeric('End Balance',
        digits=(16, Eval('currency_digits', 2)),
        states=_BALANCE_STATES, depends=_BALANCE_DEPENDS + ['currency_digits'])
    balance = fields.Function(
        fields.Numeric('Balance',
            digits=(16, Eval('currency_digits', 2)),
            states=_BALANCE_STATES,
            depends=_BALANCE_DEPENDS + ['currency_digits']),
        'on_change_with_balance')
    total_amount = fields.Numeric('Total Amount',
        digits=(16, Eval('currency_digits', 2)),
        states=_AMOUNT_STATES, depends=_AMOUNT_DEPENDS + ['currency_digits'])
    number_of_lines = fields.Integer('Number of Lines',
        states=_NUMBER_STATES, depends=_NUMBER_DEPENDS)
    lines = fields.One2Many('account.statement.line', 'statement',
        'Lines', states={
            'readonly': (Eval('state') != 'draft') | ~Eval('journal'),
            },
        depends=['state', 'journal'])
    origins = fields.One2Many('account.statement.origin', 'statement',
        "Origins", states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])
    origin_file = fields.Binary(
        "Origin File", readonly=True,
        file_id=file_id, store_prefix=store_prefix)
    origin_file_id = fields.Char("Origin File ID", readonly=True)
    state = fields.Selection(STATES, 'State', readonly=True, select=True)
    validation = fields.Function(fields.Char('Validation'),
        'on_change_with_validation')
    to_reconcile = fields.Function(
        fields.Boolean("To Reconcile"), 'get_to_reconcile')

    @classmethod
    def __setup__(cls):
        super(Statement, cls).__setup__()
        cls._order[0] = ('id', 'DESC')
        cls._error_messages.update({
                'wrong_end_balance': 'End Balance must be "%s".',
                'wrong_total_amount': 'Total Amount must be "%s".',
                'wrong_number_of_lines': 'Number of Lines must be "%s".',
                'delete_cancel': ('Statement "%s" must be cancelled before '
                    'deletion.'),
                'paid_invoice_draft_statement': ('There are paid invoices on '
                    'draft statements.'),
                'debit_credit_account_statement_journal': ('Please provide '
                    'debit and credit account on statement journal "%s".'),
                'post_with_pending_amount': ('Origin line "%(origin)s" '
                    'of statement "%(statement)s" still has a pending amount '
                    'of "%(amount)s".'),
                })
        cls._transitions |= set((
                ('draft', 'validated'),
                ('draft', 'cancel'),
                ('validated', 'posted'),
                ('validated', 'cancel'),
                ('cancel', 'draft'),
                ))
        cls._buttons.update({
                'draft': {
                    'invisible': Eval('state') != 'cancel',
                    'depends': ['state'],
                    },
                'validate_statement': {
                    'invisible': Eval('state') != 'draft',
                    'depends': ['state'],
                    },
                'post': {
                    'invisible': Eval('state') != 'validated',
                    'depends': ['state'],
                    },
                'cancel': {
                    'invisible': ~Eval('state').in_(['draft', 'validated']),
                    'depends': ['state'],
                    },
                'reconcile': {
                    'invisible': Eval('state').in_(['draft', 'cancel']),
                    'readonly': ~Eval('to_reconcile'),
                    'depends': ['state', 'to_reconcile'],
                    },
                })

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        sql_table = cls.__table__()

        # Migration from 1.8: new field company
        table = TableHandler(cls, module_name)
        company_exist = table.column_exist('company')

        super(Statement, cls).__register__(module_name)

        # Migration from 1.8: fill new field company
        if not company_exist:
            offset = 0
            limit = transaction.database.IN_MAX
            statements = True
            while statements:
                statements = cls.search([], offset=offset, limit=limit)
                offset += limit
                for statement in statements:
                    cls.write([statement], {
                            'company': statement.journal.company.id,
                            })
            table = TableHandler(cls, module_name)
            table.not_null_action('company', action='add')

        # Migration from 3.2: remove required on start/end balance
        table.not_null_action('start_balance', action='remove')
        table.not_null_action('end_balance', action='remove')

        # Migration from 3.2: add required name
        cursor.execute(*sql_table.update([sql_table.name],
                [sql_table.id.cast(cls.name.sql_type().base)],
                where=sql_table.name == Null))

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_date():
        Date = Pool().get('ir.date')
        return Date.today()

    @staticmethod
    def default_currency_digits():
        Company = Pool().get('company.company')
        if Transaction().context.get('company'):
            company = Company(Transaction().context['company'])
            return company.currency.digits
        return 2

    @fields.depends('journal', 'state', 'lines')
    def on_change_journal(self):
        if not self.journal:
            return

        statements = self.search([
                ('journal', '=', self.journal.id),
                ], order=[
                ('date', 'DESC'),
                ('id', 'DESC'),
                ], limit=1)
        if not statements:
            return

        statement, = statements
        self.start_balance = statement.end_balance

    @fields.depends('journal')
    def on_change_with_currency_digits(self, name=None):
        if self.journal:
            return self.journal.currency.digits
        return 2

    def get_end_balance(self, name):
        end_balance = self.start_balance
        for line in self.lines:
            end_balance += line.amount
        return end_balance

    @fields.depends('start_balance', 'end_balance')
    def on_change_with_balance(self, name=None):
        return ((getattr(self, 'end_balance', 0) or 0)
            - (getattr(self, 'start_balance', 0) or 0))

    @fields.depends('lines', 'journal', 'company')
    def on_change_lines(self):
        pool = Pool()
        Line = pool.get('account.statement.line')
        if not self.journal or not self.lines or not self.company:
            return
        if self.journal.currency != self.company.currency:
            return

        invoices = set()
        for line in self.lines:
            if (getattr(line, 'invoice', None)
                    and line.invoice.currency == self.company.currency):
                invoices.add(line.invoice)
        invoice_id2amount_to_pay = {}
        for invoice in invoices:
            if invoice.type == 'out':
                sign = -1
            else:
                sign = 1
            invoice_id2amount_to_pay[invoice.id] = sign * invoice.amount_to_pay

        lines = list(self.lines)
        line_offset = 0
        for index, line in enumerate(self.lines or []):
            if getattr(line, 'invoice', None) and line.id:
                if line.invoice.id not in invoice_id2amount_to_pay:
                    continue
                amount_to_pay = invoice_id2amount_to_pay[line.invoice.id]
                if (amount_to_pay
                        and getattr(line, 'amount', None)
                        and (line.amount >= 0) == (amount_to_pay <= 0)):
                    if abs(line.amount) > abs(amount_to_pay):
                        new_line = Line()
                        for field_name, field in Line._fields.iteritems():
                            if field_name == 'id':
                                continue
                            try:
                                setattr(new_line, field_name,
                                    getattr(line, field_name))
                            except AttributeError:
                                pass
                        new_line.amount = line.amount + amount_to_pay
                        new_line.invoice = None
                        line_offset += 1
                        lines.insert(index + line_offset, new_line)
                        invoice_id2amount_to_pay[line.invoice.id] = 0
                        line.amount = amount_to_pay.copy_sign(line.amount)
                    else:
                        invoice_id2amount_to_pay[line.invoice.id] = (
                            line.amount + amount_to_pay)
                else:
                    line.invoice = None
        self.lines = lines

    @fields.depends('journal')
    def on_change_with_validation(self, name=None):
        if self.journal:
            return self.journal.validation

    def get_to_reconcile(self, name=None):
        return bool(self.lines_to_reconcile)

    @property
    def lines_to_reconcile(self):
        lines = []
        for line in self.lines:
            if line.move:
                for move_line in line.move.lines:
                    if (move_line.account.reconcile
                            and not move_line.reconciliation):
                        lines.append(move_line)
        return lines

    def _group_key(self, line):
        key = (
            ('number', line.number or Unequal()),
            ('date', line.date),
            ('party', line.party),
            )
        return key

    def _get_grouped_line(self):
        "Return Line class for grouped lines"
        assert self.lines

        keys = [k[0] for k in self._group_key(self.lines[0])]

        class Line(namedtuple('Line', keys + ['lines'])):

            @property
            def amount(self):
                return sum((l.amount for l in self.lines))

            @property
            def descriptions(self):
                done = set()
                for line in self.lines:
                    if line.description and line.description not in done:
                        done.add(line.description)
                        yield line.description
        return Line

    @property
    def grouped_lines(self):
        if self.origins:
            for origin in self.origins:
                yield origin
        elif self.lines:
            Line = self._get_grouped_line()
            for key, lines in groupby(self.lines, key=self._group_key):
                yield Line(**dict(key + (('lines', list(lines)),)))

    @classmethod
    def delete(cls, statements):
        # Cancel before delete
        cls.cancel(statements)
        for statement in statements:
            if statement.state != 'cancel':
                cls.raise_user_error('delete_cancel', (statement.rec_name,))
        super(Statement, cls).delete(statements)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, statements):
        pass

    def validate_balance(self):
        pool = Pool()
        Lang = pool.get('ir.lang')

        end_balance = (self.start_balance
            + sum(l.amount for l in self.lines))
        if end_balance != self.end_balance:
            lang = Lang.get()
            amount = lang.currency(end_balance, self.journal.currency)
            self.raise_user_error('wrong_end_balance', amount)

    def validate_amount(self):
        pool = Pool()
        Lang = pool.get('ir.lang')

        amount = sum(l.amount for l in self.lines)
        if amount != self.total_amount:
            lang = Lang.get()
            amount = lang.currency(amount, self.journal.currency)
            self.raise_user_error('wrong_total_amount', amount)

    def validate_number_of_lines(self):
        number = len(list(self.grouped_lines))
        if number != self.number_of_lines:
            self.raise_user_error('wrong_number_of_lines', number)

    @classmethod
    @ModelView.button
    @Workflow.transition('validated')
    def validate_statement(cls, statements):
        pool = Pool()
        Line = pool.get('account.statement.line')

        for statement in statements:
            getattr(statement, 'validate_%s' % statement.validation)()

        cls.create_move(statements)

        cls.write(statements, {
                'state': 'validated',
                })
        common_lines = Line.search([
                ('statement.state', '=', 'draft'),
                ('invoice.state', '=', 'paid'),
                ])
        if common_lines:
            warning_key = '_'.join(str(l.id) for l in common_lines)
            cls.raise_user_warning(warning_key, 'paid_invoice_draft_statement')
            Line.write(common_lines, {
                    'invoice': None,
                    })

    @classmethod
    def create_move(cls, statements):
        '''Create move for the statements and try to reconcile the lines.
        Returns the list of move, statement and lines
        '''
        pool = Pool()
        Line = pool.get('account.statement.line')
        Move = pool.get('account.move')
        MoveLine = pool.get('account.move.line')

        moves = []
        for statement in statements:
            for key, lines in groupby(
                    statement.lines, key=statement._group_key):
                lines = list(lines)
                key = dict(key)
                move = statement._get_move(key)
                moves.append((move, statement, lines))

        Move.save([m for m, _, _ in moves])

        to_write = []
        for move, _, lines in moves:
            to_write.append(lines)
            to_write.append({
                    'move': move.id,
                    })
        if to_write:
            Line.write(*to_write)

        move_lines = []
        for move, statement, lines in moves:
            amount = 0
            amount_second_currency = 0
            for line in lines:
                move_line = line.get_move_line()
                move_line.move = move
                amount += move_line.debit - move_line.credit
                if move_line.amount_second_currency:
                    amount_second_currency += move_line.amount_second_currency
                move_lines.append((move_line, line))

            move_line = statement._get_move_line(
                amount, amount_second_currency, lines)
            move_line.move = move
            move_lines.append((move_line, None))

        MoveLine.save([l for l, _ in move_lines])

        Line.reconcile(move_lines)
        return moves

    def _get_move(self, key):
        'Return Move for the grouping key'
        pool = Pool()
        Move = pool.get('account.move')
        Period = pool.get('account.period')

        period_id = Period.find(self.company.id, date=key['date'])
        return Move(
            period=period_id,
            journal=self.journal.journal,
            date=key['date'],
            origin=self,
            company=self.company,
            description=unicode(key['number']),
            )

    def _get_move_line(self, amount, amount_second_currency, lines):
        'Return counterpart Move Line for the amount'
        pool = Pool()
        MoveLine = pool.get('account.move.line')

        if amount < 0:
            account = self.journal.journal.debit_account
        else:
            account = self.journal.journal.credit_account

        if not account:
            self.raise_user_error('debit_credit_account_statement_journal',
                (self.journal.rec_name,))

        if self.journal.currency != self.company.currency:
            second_currency = self.journal.currency
            amount_second_currency *= -1
        else:
            second_currency = None
            amount_second_currency = None

        descriptions = {l.description for l in lines}
        if len(descriptions) == 1:
            description, = descriptions
        else:
            description = ''

        return MoveLine(
            debit=abs(amount) if amount < 0 else 0,
            credit=abs(amount) if amount > 0 else 0,
            account=account,
            second_currency=second_currency,
            amount_second_currency=amount_second_currency,
            description=description,
            )

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    def post(cls, statements):
        StatementLine = Pool().get('account.statement.line')
        for statement in statements:
            for origin in statement.origins:
                if origin.pending_amount:
                    cls.raise_user_error('post_with_pending_amount', {
                            'origin': origin.rec_name,
                            'amount': origin.pending_amount,
                            'statement': statement.rec_name,
                            })

        lines = [l for s in statements for l in s.lines]
        StatementLine.post_move(lines)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, statements):
        StatementLine = Pool().get('account.statement.line')

        lines = [l for s in statements for l in s.lines]
        StatementLine.delete_move(lines)

    @classmethod
    @ModelView.button_action('account_statement.act_reconcile')
    def reconcile(cls, statements):
        pass


def origin_mixin(_states, _depends):
    class Mixin:
        statement = fields.Many2One(
            'account.statement', "Statement",
            required=True, ondelete='CASCADE', states=_states,
            depends=_depends)
        statement_state = fields.Function(
            fields.Selection('get_statement_states', "Statement State"),
            'on_change_with_statement_state')
        company = fields.Function(
            fields.Many2One('company.company', "Company"),
            'on_change_with_company', searcher='search_company')
        number = fields.Char("Number")
        date = fields.Date(
            "Date", required=True, states=_states, depends=_depends)
        amount = fields.Numeric(
            "Amount", required=True,
            digits=(16, Eval('_parent_statement', {})
                .get('currency_digits', 2)),
            states=_states, depends=_depends)
        party = fields.Many2One(
            'party.party', "Party", states=_states, depends=_depends)
        account = fields.Many2One(
            'account.account', "Account",
            domain=[
                ('company', '=', Eval('company', 0)),
                ('kind', '!=', 'view'),
                ],
            states=_states, depends=_depends + ['company'])
        description = fields.Char(
            "Description", states=_states, depends=_depends)

        @classmethod
        def get_statement_states(cls):
            pool = Pool()
            Statement = pool.get('account.statement')
            return Statement.fields_get(['state'])['state']['selection']

        @fields.depends('statement', '_parent_statement.state')
        def on_change_with_statement_state(self, name=None):
            if self.statement:
                return self.statement.state

        @fields.depends('statement', '_parent_statement.company')
        def on_change_with_company(self, name=None):
            if self.statement and self.statement.company:
                return self.statement.company.id

        @classmethod
        def search_company(cls, name, clause):
            return [('statement.' + clause[0],) + tuple(clause[1:])]

    return Mixin


_states = {
    'readonly': Eval('statement_state') != 'draft',
    }
_depends = ['statement_state']


class Line(
        origin_mixin(_states, _depends), sequence_ordered(),
        ModelSQL, ModelView):
    'Account Statement Line'
    __name__ = 'account.statement.line'

    move = fields.Many2One('account.move', 'Account Move', readonly=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    invoice = fields.Many2One('account.invoice', 'Invoice',
        domain=[
            If(Bool(Eval('party')), [('party', '=', Eval('party'))], []),
            If(Bool(Eval('account')), [('account', '=', Eval('account'))], []),
            If(Eval('statement_state') == 'draft',
                ('state', '=', 'posted'),
                ('state', '!=', '')),
            ],
        states=_states,
        depends=['party', 'account'] + _depends)
    origin = fields.Many2One('account.statement.origin', 'Origin',
        readonly=True,
        states={
            'invisible': ~Bool(Eval('origin')),
            },
        domain=[
            ('statement', '=', Eval('statement')),
            ('date', '=', Eval('date')),
            ],
        depends=['statement', 'date'])

    @classmethod
    def __setup__(cls):
        super(Line, cls).__setup__()
        if 'origin' not in cls.date.depends:
            cls.date.states.update({
                    'readonly': (cls.date.states['readonly'] |
                        Bool(Eval('origin', 0))),
                    })
            cls.date.depends.append('origin')
        cls.account.required = True
        t = cls.__table__()
        cls._sql_constraints += [
            ('check_statement_line_amount', Check(t, t.amount != 0),
                'Amount should be a positive or negative value.'),
            ]

    @staticmethod
    def default_amount():
        return Decimal(0)

    @fields.depends('amount', 'party', 'invoice')
    def on_change_party(self):
        if self.party:
            if self.amount:
                if self.amount > Decimal("0.0"):
                    self.account = self.party.account_receivable_used
                else:
                    self.account = self.party.account_payable_used

        if self.invoice:
            if self.party:
                if self.invoice.party != self.party:
                    self.invoice = None
            else:
                self.invoice = None

    @fields.depends('amount', 'party', 'account', 'invoice', 'statement',
        '_parent_statement.journal')
    def on_change_amount(self):
        Currency = Pool().get('currency.currency')
        if self.party:
            if self.account and self.account not in (
                    self.party.account_receivable_used,
                    self.party.account_payable_used):
                # The user has entered a non-default value, we keep it.
                pass
            elif self.amount:
                if self.amount > Decimal("0.0"):
                    self.account = self.party.account_receivable_used
                else:
                    self.account = self.party.account_payable_used
        if self.invoice:
            if self.amount and self.statement and self.statement.journal:
                invoice = self.invoice
                journal = self.statement.journal
                with Transaction().set_context(date=invoice.currency_date):
                    amount_to_pay = Currency.compute(invoice.currency,
                        invoice.amount_to_pay, journal.currency)
                if abs(self.amount) > amount_to_pay:
                    self.invoice = None
            else:
                self.invoice = None

    @fields.depends('account', 'invoice')
    def on_change_account(self):
        if self.invoice:
            if self.account:
                if self.invoice.account != self.account:
                    self.invoice = None
            else:
                self.invoice = None

    @fields.depends('party', 'account', 'invoice')
    def on_change_invoice(self):
        if self.invoice:
            if not self.party:
                self.party = self.invoice.party
            if not self.account:
                self.account = self.invoice.account

    @fields.depends('origin',
        '_parent_origin.pending_amount', '_parent_origin.date',
        '_parent_origin.party', '_parent_origin.account',
        '_parent_origin.number', '_parent_origin.description',
        '_parent_origin.statement',
        methods=['party'])
    def on_change_origin(self):
        if self.origin:
            self.amount = self.origin.pending_amount
            self.date = self.origin.date
            self.party = self.origin.party
            self.number = self.origin.number
            self.description = self.origin.description
            self.statement = self.origin.statement
            if self.origin.account:
                self.account = self.origin.account
            else:
                self.on_change_party()

    @fields.depends('origin', '_parent_origin.company')
    def on_change_with_company(self, name=None):
        try:
            company = super(Line, self).on_change_with_company()
        except AttributeError:
            company = None
        if self.origin and self.origin.company:
            return self.origin.company.id
        return company

    @fields.depends('origin', '_parent_origin.state')
    def on_change_with_statement_state(self, name=None):
        try:
            state = super(Line, self).on_change_with_statement_state()
        except AttributeError:
            state = None
        if self.origin:
            return self.origin.statement_state
        return state

    def get_rec_name(self, name):
        return self.statement.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('statement.rec_name',) + tuple(clause[1:])]

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default.setdefault('move', None)
        default.setdefault('invoice', None)
        return super(Line, cls).copy(lines, default=default)

    @classmethod
    def reconcile(cls, move_lines):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        MoveLine = pool.get('account.move.line')

        invoice_payments = defaultdict(list)

        to_reconcile = []
        for move_line, line in move_lines:
            if not line or not line.invoice:
                continue

            # Write previous invoice payments to have them when calling
            # get_reconcile_lines_for_amount
            if line.invoice in invoice_payments:
                Invoice.add_payment_lines(invoice_payments)
                invoice_payments.clear()

            reconcile_lines = line.invoice.get_reconcile_lines_for_amount(
                move_line.credit - move_line.debit)

            assert move_line.account == line.invoice.account

            invoice_payments[line.invoice].append(move_line.id)
            if not reconcile_lines[1]:
                to_reconcile.append(reconcile_lines[0] + [move_line])
        if invoice_payments:
            Invoice.add_payment_lines(invoice_payments)
        if to_reconcile:
            MoveLine.reconcile(*to_reconcile)

    @classmethod
    def post_move(cls, lines):
        Move = Pool().get('account.move')
        Move.post(list({l.move for l in lines if l.move}))

    @classmethod
    def delete_move(cls, lines):
        pool = Pool()
        Move = pool.get('account.move')
        Reconciliation = pool.get('account.move.reconciliation')

        reconciliations = [l.reconciliation
            for line in lines for l in line.move.lines
            if line.move and l.reconciliation]
        Reconciliation.delete(reconciliations)
        Move.delete(list({l.move for l in lines if l.move}))

    def get_move_line(self):
        '''
        Return the move line for the statement line
        '''
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Currency = Pool().get('currency.currency')
        zero = Decimal("0.0")
        with Transaction().set_context(date=self.date):
            amount = Currency.compute(self.statement.journal.currency,
                self.amount, self.statement.company.currency)
        if self.statement.journal.currency != self.statement.company.currency:
            second_currency = self.statement.journal.currency.id
            amount_second_currency = -self.amount
        else:
            amount_second_currency = None
            second_currency = None

        return MoveLine(
            description=self.description,
            debit=amount < zero and -amount or zero,
            credit=amount >= zero and amount or zero,
            account=self.account,
            party=self.party if self.account.party_required else None,
            second_currency=second_currency,
            amount_second_currency=amount_second_currency,
            )

del _states, _depends


class LineGroup(ModelSQL, ModelView):
    'Account Statement Line Group'
    __name__ = 'account.statement.line.group'
    _rec_name = 'number'
    statement = fields.Many2One('account.statement', 'Statement')
    journal = fields.Function(fields.Many2One('account.statement.journal',
            'Journal'), 'get_journal', searcher='search_journal')
    number = fields.Char('Number')
    date = fields.Date('Date')
    amount = fields.Numeric('Amount',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    currency = fields.Function(fields.Many2One('currency.currency',
            'Currency'), 'get_currency')
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'get_currency_digits')
    party = fields.Many2One('party.party', 'Party')
    move = fields.Many2One('account.move', 'Move')

    @classmethod
    def __setup__(cls):
        super(LineGroup, cls).__setup__()
        cls._order.insert(0, ('date', 'DESC'))

    @classmethod
    def _grouped_columns(cls, line):
        return [
            Max(line.statement).as_('statement'),
            Max(line.number).as_('number'),
            Max(line.date).as_('date'),
            Sum(line.amount).as_('amount'),
            Max(line.party).as_('party'),
            ]

    @classmethod
    def table_query(cls):
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.statement.line')
        move = Move.__table__()
        line = Line.__table__()

        std_columns = [
            move.id,
            move.create_uid,
            move.create_date,
            move.write_uid,
            move.write_date,
            ]

        columns = (std_columns + [move.id.as_('move')]
            + cls._grouped_columns(line))
        return move.join(line,
            condition=move.id == line.move
            ).select(*columns,
                where=move.origin.ilike(Statement.__name__ + ',%'),
                group_by=std_columns + [move.id]
                )

    def get_journal(self, name):
        return self.statement.journal.id

    @classmethod
    def search_journal(cls, name, clause):
        return [('statement.' + clause[0],) + tuple(clause[1:])]

    def get_currency(self, name):
        return self.statement.journal.currency.id

    def get_currency_digits(self, name):
        return self.statement.journal.currency.digits


_states = {
    'readonly': (Eval('statement_state') != 'draft') | Eval('lines', []),
    }
_depends = ['statement_state']


class Origin(origin_mixin(_states, _depends), ModelSQL, ModelView):
    "Account Statement Origin"
    __name__ = 'account.statement.origin'
    _rec_name = 'number'

    lines = fields.One2Many(
        'account.statement.line', 'origin', "Lines",
        states={
            'readonly': ((Eval('statement_id', -1) < 0) |
                ~Eval('statement_state').in_(['draft', 'validated'])),
            },
        domain=[
            ('statement', '=', Eval('statement')),
            ('date', '=', Eval('date')),
            ],
        depends=['statement', 'date', 'statement_id'])
    statement_id = fields.Function(
        fields.Integer("Statement ID"), 'on_change_with_statement_id')
    pending_amount = fields.Function(
        fields.Numeric("Pending Amount",
            digits=(16, Eval('_parent_statement', {})
                .get('currency_digits', 2))),
        'on_change_with_pending_amount', searcher='search_pending_amount')
    informations = fields.Dict(
        'account.statement.origin.information', "Informations", readonly=True)

    @fields.depends('statement')
    def on_change_with_statement_id(self, name=None):
        if self.statement:
            return self.statement.id
        return -1

    @fields.depends('lines', 'amount')
    def on_change_with_pending_amount(self, name=None):
        lines_amount = sum(
            getattr(l, 'amount') or Decimal(0) for l in self.lines)
        return (self.amount or Decimal(0)) - lines_amount

    @classmethod
    def search_pending_amount(cls, name, clause):
        pool = Pool()
        Line = pool.get('account.statement.line')
        table = cls.__table__()
        line = Line.__table__()

        _, operator, value = clause
        Operator = fields.SQL_OPERATORS[operator]

        query = (table.join(line, 'LEFT', condition=line.origin == table.id)
            .select(table.id,
                having=Operator(
                    table.amount - Coalesce(Sum(line.amount), 0), value),
                group_by=table.id))
        return [('id', 'in', query)]
del _states, _depends


class OriginInformation(DictSchemaMixin, ModelSQL, ModelView):
    "Statement Origin Information"
    __name__ = 'account.statement.origin.information'


class ImportStatementStart(ModelView):
    "Statement Import Start"
    __name__ = 'account.statement.import.start'
    company = fields.Many2One('company.company', "Company", required=True)
    file_ = fields.Binary("File", required=True)
    file_format = fields.Selection([(None, '')], 'File Format', required=True)

    @classmethod
    def default_file_format(cls):
        return None

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')


class ImportStatement(Wizard):
    "Statement Import"
    __name__ = 'account.statement.import'
    start = StateView('account.statement.import.start',
        'account_statement.statement_import_start_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Import", 'import_', 'tryton-ok', default=True),
            ])
    import_ = StateAction('account_statement.act_statement_form')

    def do_import_(self, action):
        pool = Pool()
        Statement = pool.get('account.statement')
        statements = list(getattr(self, 'parse_%s' % self.start.file_format)())
        for statement in statements:
            statement.origin_file = fields.Binary.cast(self.start.file_)
        Statement.save(statements)

        data = {'res_id': map(int, statements)}
        if len(statements) == 1:
            action['views'].reverse()
        return action, data


class ReconcileStatement(Wizard):
    "Statement Reconcile"
    __name__ = 'account.statement.reconcile'
    start = StateAction('account.act_reconcile')

    def do_start(self, action):
        pool = Pool()
        Statement = pool.get('account.statement')
        statements = Statement.browse(Transaction().context['active_ids'])
        lines = sum(([int(l) for l in s.lines_to_reconcile]
                for s in statements), [])
        return action, {
            'model': 'account.move.line',
            'ids': lines,
            }


class StatementReport(CompanyReport):
    __name__ = 'account.statement'
