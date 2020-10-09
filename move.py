# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
import datetime
from itertools import groupby, combinations, chain
from operator import itemgetter
from collections import defaultdict

from sql import Null, Literal
from sql.aggregate import Sum, Max
from sql.functions import CharLength
from sql.conditionals import Coalesce, Case

from trytond.i18n import gettext
from trytond.model import ModelView, ModelSQL, fields, Check, DeactivableMixin
from trytond.model.exceptions import AccessError
from trytond.wizard import Wizard, StateTransition, StateView, StateAction, \
    StateReport, Button
from trytond.report import Report
from trytond import backend
from trytond.pyson import Eval, Bool, If, PYSONEncoder
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.rpc import RPC
from trytond.tools import reduce_ids, grouped_slice
from trytond.config import config

from .exceptions import (PostError, MoveDatesError, CancelWarning,
    ReconciliationError, DeleteDelegatedWarning, GroupLineError)

__all__ = ['Move', 'Reconciliation', 'Line', 'WriteOff', 'OpenJournalAsk',
    'OpenJournal', 'OpenAccount',
    'ReconcileLinesWriteOff', 'ReconcileLines',
    'UnreconcileLines',
    'Reconcile', 'ReconcileShow',
    'CancelMoves', 'CancelMovesDefault',
    'GroupLines', 'GroupLinesStart',
    'PrintGeneralJournalStart', 'PrintGeneralJournal', 'GeneralJournal']

_MOVE_STATES = {
    'readonly': Eval('state') == 'posted',
    }
_MOVE_DEPENDS = ['state']
_LINE_STATES = {
    'readonly': Eval('state') == 'valid',
    }
_LINE_DEPENDS = ['state']


class Move(ModelSQL, ModelView):
    'Account Move'
    __name__ = 'account.move'
    _rec_name = 'number'
    number = fields.Char('Number', required=True, readonly=True)
    post_number = fields.Char('Post Number', readonly=True,
        help='Also known as Folio Number')
    company = fields.Many2One('company.company', 'Company', required=True,
        states=_MOVE_STATES, depends=_MOVE_DEPENDS)
    period = fields.Many2One('account.period', 'Period', required=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            If(Eval('state') == 'draft',
                ('state', '=', 'open'),
                ()),
            ],
        states=_MOVE_STATES, depends=_MOVE_DEPENDS + ['company', 'state'],
        select=True)
    journal = fields.Many2One('account.journal', 'Journal', required=True,
            states=_MOVE_STATES, depends=_MOVE_DEPENDS)
    date = fields.Date('Effective Date', required=True, select=True,
        states=_MOVE_STATES, depends=_MOVE_DEPENDS)
    post_date = fields.Date('Post Date', readonly=True)
    description = fields.Char('Description', states=_MOVE_STATES,
        depends=_MOVE_DEPENDS)
    origin = fields.Reference('Origin', selection='get_origin',
        states=_MOVE_STATES, depends=_MOVE_DEPENDS)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ], 'State', required=True, readonly=True, select=True)
    lines = fields.One2Many('account.move.line', 'move', 'Lines',
        domain=[
            ('account.company', '=', Eval('company', -1)),
            ],
        states=_MOVE_STATES, depends=_MOVE_DEPENDS + ['company'],
            context={
                'journal': Eval('journal'),
                'period': Eval('period'),
                'date': Eval('date'),
            })

    @classmethod
    def __setup__(cls):
        super(Move, cls).__setup__()
        cls._check_modify_exclude = []
        cls._order.insert(0, ('date', 'DESC'))
        cls._order.insert(1, ('number', 'DESC'))
        cls._buttons.update({
                'post': {
                    'invisible': Eval('state') == 'posted',
                    'depends': ['state'],
                    },
                })
        cls.__rpc__.update({
                'post': RPC(
                    readonly=False, instantiate=0, fresh_session=True),
                })

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        table = cls.__table_handler__(module_name)
        sql_table = cls.__table__()
        pool = Pool()
        Period = pool.get('account.period')
        period = Period.__table__()
        FiscalYear = pool.get('account.fiscalyear')
        fiscalyear = FiscalYear.__table__()

        created_company = not table.column_exist('company')

        super(Move, cls).__register__(module_name)

        # Migration from 3.4: new company field
        if created_company:
            # Don't use UPDATE FROM because SQLite nor MySQL support it.
            value = period.join(fiscalyear,
                condition=period.fiscalyear == fiscalyear.id).select(
                    fiscalyear.company,
                    where=period.id == sql_table.period)
            cursor.execute(*sql_table.update([sql_table.company], [value]))

        table = cls.__table_handler__(module_name)
        table.index_action(['journal', 'period'], 'add')

        # Add index on create_date
        table.index_action('create_date', action='add')

    @classmethod
    def order_post_number(cls, tables):
        table, _ = tables[None]
        return [CharLength(table.post_number), table.post_number]

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_period():
        Period = Pool().get('account.period')
        return Period.find(Transaction().context.get('company'),
            exception=False)

    @staticmethod
    def default_state():
        return 'draft'

    @classmethod
    def default_date(cls):
        pool = Pool()
        Period = pool.get('account.period')
        Date = pool.get('ir.date')
        today = Date.today()
        period_id = cls.default_period()
        if period_id:
            period = Period(period_id)
            if today < period.start_date or today > period.end_date:
                return period.start_date
        return today

    @fields.depends('period', 'journal', 'date')
    def on_change_with_date(self):
        pool = Pool()
        Line = pool.get('account.move.line')
        Date = pool.get('ir.date')
        today = Date.today()
        date = self.date
        if date:
            if self.period and not (
                    self.period.start_date <= date <= self.period.end_date):
                if (today >= self.period.start_date
                        and today <= self.period.end_date):
                    date = today
                else:
                    date = self.period.start_date
                self.on_change_date()
            return date
        lines = Line.search([
                ('journal', '=', self.journal),
                ('period', '=', self.period),
                ], order=[('id', 'DESC')], limit=1)
        if lines:
            date = lines[0].date
        elif self.period:
            if (today >= self.period.start_date
                    and today <= self.period.end_date):
                date = today
            else:
                date = self.period.start_date
        return date

    @fields.depends('date', 'lines')
    def on_change_date(self):
        for line in (self.lines or []):
            line.date = self.date

    @fields.depends(methods=['on_change_with_date', 'on_change_date'])
    def on_change_period(self):
        self.date = self.on_change_with_date()
        self.on_change_date()

    @classmethod
    def _get_origin(cls):
        'Return list of Model names for origin Reference'
        return ['account.fiscalyear', 'account.move']

    @classmethod
    def get_origin(cls):
        Model = Pool().get('ir.model')
        models = cls._get_origin()
        models = Model.search([
                ('model', 'in', models),
                ])
        return [('', '')] + [(m.model, m.name) for m in models]

    @classmethod
    def validate(cls, moves):
        super(Move, cls).validate(moves)
        for move in moves:
            move.check_date()

    def check_date(self):
        if (self.date < self.period.start_date
                or self.date > self.period.end_date):
            raise MoveDatesError(
                gettext('account.msg_move_date_outside_period',
                    move=self.rec_name))

    @classmethod
    def check_modify(cls, moves):
        'Check posted moves for modifications.'
        for move in moves:
            if move.state == 'posted':
                raise AccessError(
                    gettext('account.msg_modify_posted_moved',
                        move=move.rec_name))

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('post_number',) + tuple(clause[1:]),
            (cls._rec_name,) + tuple(clause[1:]),
            ]

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        all_moves = []
        args = []
        for moves, values in zip(actions, actions):
            keys = list(values.keys())
            for key in cls._check_modify_exclude:
                if key in keys:
                    keys.remove(key)
            if len(keys):
                cls.check_modify(moves)
            args.extend((moves, values))
            all_moves.extend(moves)
        super(Move, cls).write(*args)
        cls.validate_move(all_moves)

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Journal = pool.get('account.journal')

        vlist = [x.copy() for x in vlist]
        for vals in vlist:
            if not vals.get('number'):
                journal_id = (vals.get('journal')
                        or Transaction().context.get('journal'))
                if journal_id:
                    journal = Journal(journal_id)
                    if journal.sequence:
                        vals['number'] = Sequence.get_id(journal.sequence.id)

        moves = super(Move, cls).create(vlist)
        cls.validate_move(moves)
        return moves

    @classmethod
    def delete(cls, moves):
        MoveLine = Pool().get('account.move.line')
        cls.check_modify(moves)
        MoveLine.delete([l for m in moves for l in m.lines])
        super(Move, cls).delete(moves)

    @classmethod
    def copy(cls, moves, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('number', None)
        default.setdefault('post_number', None)
        default.setdefault('state', cls.default_state())
        default.setdefault('post_date', None)
        return super().copy(moves, default=default)

    @classmethod
    def validate_move(cls, moves):
        '''
        Validate balanced move
        '''
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        line = MoveLine.__table__()

        cursor = Transaction().connection.cursor()

        amounts = {}
        move2draft_lines = {}
        for sub_move_ids in grouped_slice([m.id for m in moves]):
            red_sql = reduce_ids(line.move, sub_move_ids)

            cursor.execute(*line.select(line.move,
                    Sum(line.debit - line.credit),
                    where=red_sql,
                    group_by=line.move))
            amounts.update(dict(cursor.fetchall()))

            cursor.execute(*line.select(line.move, line.id,
                    where=red_sql & (line.state == 'draft'),
                    order_by=line.move))
            move2draft_lines.update(dict((k, [j[1] for j in g])
                    for k, g in groupby(cursor.fetchall(), itemgetter(0))))

        valid_moves = []
        draft_moves = []
        for move in moves:
            if move.id not in amounts:
                continue
            amount = amounts[move.id]
            # SQLite uses float for SUM
            if not isinstance(amount, Decimal):
                amount = Decimal(amount)
            draft_lines = MoveLine.browse(move2draft_lines.get(move.id, []))
            if not move.company.currency.is_zero(amount):
                draft_moves.append(move.id)
                continue
            if not draft_lines:
                continue
            valid_moves.append(move.id)
        for move_ids, state in (
                (valid_moves, 'valid'),
                (draft_moves, 'draft'),
                ):
            if move_ids:
                for sub_ids in grouped_slice(move_ids):
                    red_sql = reduce_ids(line.move, sub_ids)
                    # Use SQL to prevent double validate loop
                    cursor.execute(*line.update(
                            columns=[line.state],
                            values=[state],
                            where=red_sql))

    def _cancel_default(self):
        'Return default dictionary to cancel move'
        pool = Pool()
        Date = pool.get('ir.date')
        Period = pool.get('account.period')
        Warning = pool.get('res.user.warning')

        default = {
            'origin': str(self),
            }
        if self.period.state == 'close':
            key = '%s.cancel' % self
            if Warning.check(key):
                raise CancelWarning(key,
                    gettext('account.msg_move_cancel_closed_period',
                        move=self.rec_name))
            date = Date.today()
            period_id = Period.find(self.company.id, date=date)
            default.update({
                    'date': date,
                    'period': period_id,
                    })
        default['lines.debit'] = lambda data: data['debit'] * -1
        default['lines.credit'] = lambda data: data['credit'] * -1
        default['lines.amount_second_currency'] = (
            lambda data: data['amount_second_currency'] * -1
            if data['amount_second_currency']
            else data['amount_second_currency'])
        default['lines.tax_lines.amount'] = lambda data: data['amount'] * -1
        default['lines.origin'] = (
            lambda data: 'account.move.line,%s' % data['id'])
        return default

    def cancel(self, default=None):
        'Return a cancel move'
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.update(self._cancel_default())
        cancel_move, = self.copy([self], default=default)
        return cancel_move

    @classmethod
    @ModelView.button
    def post(cls, moves):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Date = pool.get('ir.date')
        Line = pool.get('account.move.line')

        for move in moves:
            amount = Decimal('0.0')
            if not move.lines:
                raise PostError(
                    gettext('account.msg_post_empty_move', move=move.rec_name))
            company = None
            for line in move.lines:
                amount += line.debit - line.credit
                if not company:
                    company = line.account.company
            if not company.currency.is_zero(amount):
                raise PostError(
                    gettext('account.msg_post_unbalanced_move',
                        move=move.rec_name))
        for move in moves:
            move.state = 'posted'
            if not move.post_number:
                move.post_date = Date.today()
                move.post_number = Sequence.get_id(
                    move.period.post_move_sequence_used.id)

            keyfunc = lambda l: (l.party, l.account)
            to_reconcile = [l for l in move.lines
                if ((l.debit == l.credit == Decimal('0'))
                    and l.account.reconcile)]
            to_reconcile = sorted(to_reconcile, key=keyfunc)
            for _, zero_lines in groupby(to_reconcile, keyfunc):
                Line.reconcile(list(zero_lines))
        cls.save(moves)


class Reconciliation(ModelSQL, ModelView):
    'Account Move Reconciliation Lines'
    __name__ = 'account.move.reconciliation'
    name = fields.Char('Name', size=None, required=True)
    lines = fields.One2Many('account.move.line', 'reconciliation',
            'Lines')
    date = fields.Date('Date', required=True, select=True,
        help='Highest date of the reconciled lines')
    delegate_to = fields.Many2One(
        'account.move.line', "Delegate To", ondelete="RESTRICT", select=True,
        help="The line to which the reconciliation status is delegated.")

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        table = cls.__table_handler__(module_name)
        sql_table = cls.__table__()
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        move = Move.__table__()
        line = Line.__table__()

        date_exist = table.column_exist('date')

        super(Reconciliation, cls).__register__(module_name)

        # Migration from 3.8: new date field
        if (not date_exist
                and TableHandler.table_exist(Line._table)
                and Line.__table_handler__().column_exist('move')):
            cursor.execute(*sql_table.update(
                    [sql_table.date],
                    line.join(move,
                        condition=move.id == line.move
                        ).select(Max(move.date),
                        where=line.reconciliation == sql_table.id,
                        group_by=line.reconciliation)))

    @classmethod
    def create(cls, vlist):
        Sequence = Pool().get('ir.sequence')

        vlist = [x.copy() for x in vlist]
        for vals in vlist:
            if 'name' not in vals:
                vals['name'] = Sequence.get('account.move.reconciliation')

        return super(Reconciliation, cls).create(vlist)

    @classmethod
    def write(cls, moves, values, *args):
        raise AccessError(gettext('account.msg_write_reconciliation'))

    @classmethod
    def validate(cls, reconciliations):
        super(Reconciliation, cls).validate(reconciliations)
        cls.check_lines(reconciliations)

    @classmethod
    def delete(cls, reconciliations):
        pool = Pool()
        Warning = pool.get('res.user.warning')
        for reconciliation in reconciliations:
            if reconciliation.delegate_to:
                key = '%s.delete.delegated' % reconciliation
                if Warning.check(key):
                    raise DeleteDelegatedWarning(key,
                        gettext('account.msg_reconciliation_delete_delegated',
                            reconciliation=reconciliation.rec_name,
                            line=reconciliation.delegate_to.rec_name,
                            move=reconciliation.delegate_to.move.rec_name))
        super().delete(reconciliations)

    @classmethod
    def check_lines(cls, reconciliations):
        Lang = Pool().get('ir.lang')
        for reconciliation in reconciliations:
            debit = Decimal('0.0')
            credit = Decimal('0.0')
            account = None
            if reconciliation.lines:
                party = reconciliation.lines[0].party
            for line in reconciliation.lines:
                if line.state != 'valid':
                    raise ReconciliationError(
                        gettext('account.msg_reconciliation_line_not_valid',
                            line=line.rec_name))
                debit += line.debit
                credit += line.credit
                if not account:
                    account = line.account
                elif account.id != line.account.id:
                    raise ReconciliationError(
                        gettext('account'
                            '.msg_reconciliation_different_accounts',
                            line=line.rec_name,
                            account1=line.account.rec_name,
                            account2=account.rec_name))
                if not account.reconcile:
                    raise ReconciliationError(
                        gettext('account'
                            '.msg_reconciliation_account_not_reconcile',
                            line=line.rec_name,
                            account=line.account.rec_name))
                if line.party != party:
                    raise ReconciliationError(
                        gettext('account'
                            '.msg_reconciliation_different_parties',
                            line=line.rec_name,
                            party1=line.party.rec_name,
                            party2=party.rec_name))
            if (account
                    and not account.company.currency.is_zero(debit - credit)):
                lang = Lang.get()
                debit = lang.currency(debit, account.company.currency)
                credit = lang.currency(credit, account.company.currency)
                raise ReconciliationError(
                    gettext('account.msg_reconciliation_unbalanced',
                        debit=debit,
                        credit=credit))


class Line(ModelSQL, ModelView):
    'Account Move Line'
    __name__ = 'account.move.line'

    _states = {
        'readonly': Eval('move_state') == 'posted',
        }
    _depends = ['move_state']

    debit = fields.Numeric('Debit', digits=(16, Eval('currency_digits', 2)),
        required=True, states=_states,
        depends=['currency_digits', 'credit', 'tax_lines', 'journal'] +
        _depends)
    credit = fields.Numeric('Credit', digits=(16, Eval('currency_digits', 2)),
        required=True, states=_states,
        depends=['currency_digits', 'debit', 'tax_lines', 'journal'] +
        _depends)
    account = fields.Many2One('account.account', 'Account', required=True,
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ['OR',
                ('start_date', '=', None),
                ('start_date', '<=', Eval('date', None)),
                ],
            ['OR',
                ('end_date', '=', None),
                ('end_date', '>=', Eval('date', None)),
                ],
            ],
        select=True, states=_states, depends=_depends + ['date'])
    move = fields.Many2One('account.move', 'Move', select=True, required=True,
        ondelete='CASCADE',
        states={
            'required': False,
            'readonly': (((Eval('state') == 'valid') | _states['readonly'])
                & Bool(Eval('move'))),
            },
        depends=['state'] + _depends)
    journal = fields.Function(fields.Many2One('account.journal', 'Journal',
            states=_states, depends=_depends),
            'get_move_field', setter='set_move_field',
            searcher='search_move_field')
    period = fields.Function(fields.Many2One('account.period', 'Period',
            states=_states, depends=_depends),
            'get_move_field', setter='set_move_field',
            searcher='search_move_field')
    date = fields.Function(fields.Date('Effective Date', required=True,
            states=_states, depends=_depends),
            'on_change_with_date', setter='set_move_field',
            searcher='search_move_field')
    origin = fields.Reference(
        "Origin", selection='get_origin', states=_states, depends=_depends)
    move_origin = fields.Function(
        fields.Reference("Move Origin", selection='get_move_origin'),
        'get_move_field', searcher='search_move_field')
    description = fields.Char('Description', states=_states, depends=_depends)
    move_description = fields.Function(fields.Char('Move Description',
            states=_states, depends=_depends),
        'get_move_field', setter='set_move_field',
        searcher='search_move_field')
    amount_second_currency = fields.Numeric('Amount Second Currency',
        digits=(16, Eval('second_currency_digits', 2)),
        help='The amount expressed in a second currency',
        states={
            'required': Bool(Eval('second_currency')),
            'readonly': _states['readonly'],
            },
        depends=['second_currency_digits', 'second_currency'] + _depends)
    second_currency = fields.Many2One('currency.currency', 'Second Currency',
            help='The second currency',
        domain=[
            If(~Eval('second_currency_required'),
                (),
                ('id', '=', Eval('second_currency_required', -1))),
            ],
        states={
            'required': (Bool(Eval('amount_second_currency'))
                | Bool(Eval('second_currency_required'))),
            'readonly': _states['readonly']
            },
        depends=['amount_second_currency', 'second_currency_required']
        + _depends)
    second_currency_required = fields.Function(
        fields.Many2One('currency.currency', "Second Currency Required"),
        'on_change_with_second_currency_required')
    party = fields.Many2One('party.party', 'Party', select=True,
        states={
            'required': Eval('party_required', False),
            'invisible': ~Eval('party_required', False),
            'readonly': _states['readonly'],
            },
        depends=['party_required'] + _depends, ondelete='RESTRICT')
    party_required = fields.Function(fields.Boolean('Party Required'),
        'on_change_with_party_required')
    maturity_date = fields.Date('Maturity Date',
        help='This field is used for payable and receivable lines. \n'
        'You can put the limit date for the payment.')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('valid', 'Valid'),
        ], 'State', readonly=True, required=True, select=True)
    reconciliation = fields.Many2One('account.move.reconciliation',
            'Reconciliation', readonly=True, ondelete='SET NULL', select=True)
    reconciliations_delegated = fields.One2Many(
        'account.move.reconciliation', 'delegate_to',
        "Reconciliations Delegated", readonly=True)
    tax_lines = fields.One2Many('account.tax.line', 'move_line', 'Tax Lines')
    move_state = fields.Function(fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ], 'Move State'), 'on_change_with_move_state',
        searcher='search_move_field')
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
            'on_change_with_currency_digits')
    second_currency_digits = fields.Function(fields.Integer(
        'Second Currency Digits'), 'on_change_with_second_currency_digits')
    amount = fields.Function(fields.Numeric('Amount',
            digits=(16, Eval('amount_currency_digits', 2)),
            depends=['amount_currency_digits']),
        'get_amount')
    amount_currency = fields.Function(fields.Many2One('currency.currency',
            'Amount Currency'), 'get_amount_currency')
    amount_currency_digits = fields.Function(fields.Integer(
            'Amount Currency Digits'), 'get_amount_currency')

    del _states, _depends

    @classmethod
    def __setup__(cls):
        super(Line, cls).__setup__()
        cls._check_modify_exclude = {
            'maturity_date', 'reconciliation', 'tax_lines'}
        cls._reconciliation_modify_disallow = {
            'account', 'debit', 'credit', 'party',
            }
        table = cls.__table__()
        cls._sql_constraints += [
            ('credit_debit',
                Check(table, table.credit * table.debit == 0),
                'account.msg_line_debit_credit'),
            ('second_currency_sign',
                Check(table, Coalesce(table.amount_second_currency, 0)
                    * (table.debit - table.credit) >= 0),
                'account.msg_line_second_currency_sign'),
            ]
        cls.__rpc__.update({
                'on_write': RPC(instantiate=0),
                })
        cls._order[0] = ('id', 'DESC')

    @classmethod
    def __register__(cls, module_name):
        super(Line, cls).__register__(module_name)

        table = cls.__table_handler__(module_name)
        # Index for General Ledger
        table.index_action(['move', 'account'], 'add')

    @classmethod
    def default_date(cls):
        '''
        Return the date of the last line for journal, period
        or the starting date of the period
        or today
        '''
        pool = Pool()
        Period = pool.get('account.period')
        Date = pool.get('ir.date')

        date = Date.today()
        lines = cls.search([
                ('journal', '=', Transaction().context.get('journal')),
                ('period', '=', Transaction().context.get('period')),
                ], order=[('id', 'DESC')], limit=1)
        if lines:
            date = lines[0].date
        elif Transaction().context.get('period'):
            period = Period(Transaction().context['period'])
            date = period.start_date
        if Transaction().context.get('date'):
            date = Transaction().context['date']
        return date

    @classmethod
    def default_move(cls):
        transaction = Transaction()
        context = transaction.context
        if context.get('journal') and context.get('period'):
            lines = cls.search([
                    ('move.journal', '=', context['journal']),
                    ('move.period', '=', context['period']),
                    ('create_uid', '=', transaction.user),
                    ('state', '=', 'draft'),
                    ], order=[('id', 'DESC')], limit=1)
            if lines:
                line, = lines
                return line.move.id

    @fields.depends('move', 'debit', 'credit', '_parent_move.lines')
    def on_change_move(self):
        if self.move and not self.debit and not self.credit:
            total = sum(l.debit - l.credit
                for l in getattr(self.move, 'lines', []))
            self.debit = -total if total < 0 else Decimal(0)
            self.credit = total if total > 0 else Decimal(0)

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_currency_digits():
        return 2

    @staticmethod
    def default_debit():
        return Decimal(0)

    @staticmethod
    def default_credit():
        return Decimal(0)

    @fields.depends('account')
    def on_change_with_currency_digits(self, name=None):
        if self.account:
            return self.account.currency_digits
        else:
            return 2

    @fields.depends('second_currency')
    def on_change_with_second_currency_digits(self, name=None):
        if self.second_currency:
            return self.second_currency.digits
        else:
            return 2

    @classmethod
    def _get_origin(cls):
        'Return list of Model names for origin Reference'
        return ['account.move.line']

    @classmethod
    def get_origin(cls):
        Model = Pool().get('ir.model')
        models = cls._get_origin()
        models = Model.search([
                ('model', 'in', models),
                ])
        return [('', '')] + [(m.model, m.name) for m in models]

    @classmethod
    def get_move_origin(cls):
        Move = Pool().get('account.move')
        return Move.get_origin()

    @fields.depends('debit', 'credit', 'amount_second_currency')
    def on_change_debit(self):
        if self.debit:
            self.credit = Decimal('0.0')
        self._amount_second_currency_sign()

    @fields.depends('debit', 'credit', 'amount_second_currency')
    def on_change_credit(self):
        if self.credit:
            self.debit = Decimal('0.0')
        self._amount_second_currency_sign()

    @fields.depends('amount_second_currency', 'debit', 'credit')
    def on_change_amount_second_currency(self):
        self._amount_second_currency_sign()

    def _amount_second_currency_sign(self):
        'Set correct sign to amount_second_currency'
        if self.amount_second_currency:
            self.amount_second_currency = \
                self.amount_second_currency.copy_sign(self.debit - self.credit)

    @fields.depends('account')
    def on_change_account(self):
        if self.account:
            self.currency_digits = self.account.currency_digits
            if self.account.second_currency:
                self.second_currency = self.account.second_currency
                self.second_currency_digits = (
                    self.on_change_with_second_currency_digits())
            if not self.account.party_required:
                self.party = None

    @fields.depends('account')
    def on_change_with_second_currency_required(self, name=None):
        if self.account and self.account.second_currency:
            return self.account.second_currency.id

    @fields.depends('account')
    def on_change_with_party_required(self, name=None):
        if self.account:
            return self.account.party_required
        return False

    def get_move_field(self, name):
        field = getattr(self.__class__, name)
        if name.startswith('move_'):
            name = name[5:]
        value = getattr(self.move, name)
        if isinstance(value, ModelSQL):
            if field._type == 'reference':
                return str(value)
            return value.id
        return value

    @fields.depends('move', '_parent_move.date')
    def on_change_with_date(self, name=None):
        if self.move:
            return self.move.date

    @classmethod
    def set_move_field(cls, lines, name, value):
        if name.startswith('move_'):
            name = name[5:]
        if not value:
            return
        Move = Pool().get('account.move')
        Move.write([line.move for line in lines], {
                name: value,
                })

    @classmethod
    def search_move_field(cls, name, clause):
        nested = clause[0].lstrip(name)
        if name.startswith('move_'):
            name = name[5:]
        return [('move.' + name + nested,) + tuple(clause[1:])]

    @fields.depends('move', '_parent_move.state')
    def on_change_with_move_state(self, name=None):
        if self.move:
            return self.move.state

    def _order_move_field(name):
        def order_field(tables):
            pool = Pool()
            Move = pool.get('account.move')
            field = Move._fields[name]
            table, _ = tables[None]
            move_tables = tables.get('move')
            if move_tables is None:
                move = Move.__table__()
                move_tables = {
                    None: (move, move.id == table.move),
                    }
                tables['move'] = move_tables
            return field.convert_order(name, move_tables, Move)
        return staticmethod(order_field)
    order_journal = _order_move_field('journal')
    order_period = _order_move_field('period')
    order_date = _order_move_field('date')
    order_move_origin = _order_move_field('origin')
    order_move_state = _order_move_field('state')

    def get_amount(self, name):
        sign = -1 if self.account.type.statement == 'income' else 1
        if self.amount_second_currency is not None:
            return self.amount_second_currency * sign
        else:
            return (self.debit - self.credit) * sign

    def get_amount_currency(self, name):
        if self.second_currency:
            currency = self.second_currency
        else:
            currency = self.account.currency
        if name == 'amount_currency':
            return currency.id
        elif name == 'amount_currency_digits':
            return currency.digits

    def get_rec_name(self, name):
        if self.debit > self.credit:
            return self.account.rec_name
        else:
            return '(%s)' % self.account.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('account.rec_name',) + tuple(clause[1:])]

    @classmethod
    def query_get(cls, table):
        '''
        Return SQL clause and fiscal years for account move line
        depending of the context.
        table is the SQL instance of account.move.line table
        '''
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')
        Move = pool.get('account.move')
        Period = pool.get('account.period')
        move = Move.__table__()
        period = Period.__table__()
        fiscalyear = FiscalYear.__table__()
        context = Transaction().context
        company = context.get('company')

        fiscalyear_ids = []
        where = Literal(True)

        if context.get('posted'):
            where &= move.state == 'posted'

        date = context.get('date')
        from_date, to_date = context.get('from_date'), context.get('to_date')
        fiscalyear_id = context.get('fiscalyear')
        period_ids = context.get('periods')
        if date:
            fiscalyears = FiscalYear.search([
                    ('start_date', '<=', date),
                    ('end_date', '>=', date),
                    ('company', '=', company),
                    ], limit=1)
            if fiscalyears:
                fiscalyear_id = fiscalyears[0].id
            else:
                fiscalyear_id = -1
            fiscalyear_ids = list(map(int, fiscalyears))
            where &= period.fiscalyear == fiscalyear_id
            where &= move.date <= date
        elif fiscalyear_id or period_ids is not None or from_date or to_date:
            if fiscalyear_id:
                fiscalyear_ids = [fiscalyear_id]
                where &= fiscalyear.id == fiscalyear_id
            if period_ids is not None:
                where &= move.period.in_(period_ids or [None])
            if from_date:
                where &= move.date >= from_date
            if to_date:
                where &= move.date <= to_date
        else:
            where &= fiscalyear.state == 'open'
            where &= fiscalyear.company == company
            fiscalyears = FiscalYear.search([
                    ('state', '=', 'open'),
                    ('company', '=', company),
                    ])
            fiscalyear_ids = list(map(int, fiscalyears))

        # Use LEFT JOIN to allow database optimization
        # if no joined table is used in the where clause.
        return (table.move.in_(move
                .join(period, 'LEFT', condition=move.period == period.id)
                .join(fiscalyear, 'LEFT',
                    condition=period.fiscalyear == fiscalyear.id)
                .select(move.id, where=where)),
            fiscalyear_ids)

    @classmethod
    def on_write(cls, lines):
        return list(set(l.id for line in lines for l in line.move.lines))

    @classmethod
    def validate(cls, lines):
        super(Line, cls).validate(lines)
        for line in lines:
            line.check_account()

    def check_account(self):
        if not self.account.type or self.account.closed:
            raise AccessError(
                gettext('account.msg_line_closed_account',
                    account=self.account.rec_name))
        if bool(self.party) != bool(self.account.party_required):
            error = 'party_set' if self.party else 'party_required'
            raise AccessError(
                gettext('account.msg_line_%s' % error,
                    account=self.account.rec_name,
                    line=self.rec_name))

    @classmethod
    def check_journal_period_modify(cls, period, journal):
        '''
        Check if the lines can be modified or created for the journal - period
        and if there is no journal - period, create it
        '''
        JournalPeriod = Pool().get('account.journal.period')
        journal_periods = JournalPeriod.search([
                ('journal', '=', journal.id),
                ('period', '=', period.id),
                ], limit=1)
        if journal_periods:
            journal_period, = journal_periods
            if journal_period.state == 'close':
                raise AccessError(
                    gettext('account.msg_modify_line_closed_journal_period',
                        journal_period=journal_period.rec_name))
        else:
            JournalPeriod.create([{
                        'journal': journal.id,
                        'period': period.id,
                        }])

    @classmethod
    def check_modify(cls, lines, modified_fields=None):
        '''
        Check if the lines can be modified
        '''
        if (modified_fields is not None
                and modified_fields <= cls._check_modify_exclude):
            return
        journal_period_done = []
        for line in lines:
            if line.move.state == 'posted':
                raise AccessError(
                    gettext('account.msg_modify_line_posted_move',
                        line=line.rec_name,
                        move=line.move.rec_name))
            journal_period = (line.journal.id, line.period.id)
            if journal_period not in journal_period_done:
                cls.check_journal_period_modify(line.period,
                        line.journal)
                journal_period_done.append(journal_period)

    @classmethod
    def check_reconciliation(cls, lines, modified_fields=None):
        if (modified_fields is not None
                and not modified_fields & cls._reconciliation_modify_disallow):
            return
        for line in lines:
            if line.reconciliation:
                raise AccessError(
                    gettext('account.msg_modify_line_reconciled',
                        line=line.rec_name))

    @classmethod
    def delete(cls, lines):
        Move = Pool().get('account.move')
        cls.check_modify(lines)
        cls.check_reconciliation(lines)
        moves = [x.move for x in lines]
        super(Line, cls).delete(lines)
        Move.validate_move(moves)

    @classmethod
    def write(cls, *args):
        Move = Pool().get('account.move')

        actions = iter(args)
        args = []
        moves = []
        all_lines = []
        for lines, values in zip(actions, actions):
            cls.check_modify(lines, set(values.keys()))
            cls.check_reconciliation(lines, set(values.keys()))
            moves.extend((x.move for x in lines))
            all_lines.extend(lines)
            args.extend((lines, values))

        super(Line, cls).write(*args)

        Transaction().timestamp = {}
        Move.validate_move(list(set(l.move for l in all_lines) | set(moves)))

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Move = pool.get('account.move')
        move = None
        vlist = [x.copy() for x in vlist]
        for vals in vlist:
            if not vals.get('move'):
                if move is None:
                    journal_id = (vals.get('journal')
                            or Transaction().context.get('journal'))
                    move = Move()
                    move.period = vals.get('period',
                        Transaction().context.get('period'))
                    move.journal = journal_id
                    move.date = vals.get('date')
                    move.save()
                vals['move'] = move.id
            else:
                # prevent computation of default date
                vals.setdefault('date', None)
        lines = super(Line, cls).create(vlist)
        period_and_journals = set((line.period, line.journal)
            for line in lines)
        for period, journal in period_and_journals:
            cls.check_journal_period_modify(period, journal)
        # Re-browse for cache alignment
        moves = Move.browse(list(set(line.move for line in lines)))
        Move.check_modify(moves)
        Move.validate_move(moves)
        return lines

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('move', None)
        default.setdefault('reconciliation', None)
        default.setdefault('reconciliations_delegated', [])
        return super(Line, cls).copy(lines, default=default)

    @classmethod
    def view_toolbar_get(cls):
        pool = Pool()
        Template = pool.get('account.move.template')

        toolbar = super(Line, cls).view_toolbar_get()

        # Add a wizard entry for each templates
        context = Transaction().context
        company = context.get('company')
        journal = context.get('journal')
        period = context.get('period')
        if company and journal and period:
            templates = Template.search([
                    ('company', '=', company),
                    ('journal', '=', journal),
                    ])
            for template in templates:
                action = toolbar['action']
                # Use template id for action id to auto-select the template
                action.append({
                        'name': template.name,
                        'type': 'ir.action.wizard',
                        'wiz_name': 'account.move.template.create',
                        'id': template.id,
                        })
        return toolbar

    @classmethod
    def reconcile(
            cls, *lines_list, date=None, writeoff=None, description=None,
            delegate_to=None):
        """
        Reconcile each list of lines together.
        The writeoff keys are: date, method and description.
        """
        pool = Pool()
        Reconciliation = pool.get('account.move.reconciliation')
        delegate_to = delegate_to.id if delegate_to else None

        reconciliations = []
        for lines in lines_list:
            for line in lines:
                if line.reconciliation:
                    raise AccessError(
                        gettext('account.msg_line_already_reconciled',
                            line=line.rec_name))

            lines = list(lines)
            reconcile_account = None
            reconcile_party = None
            amount = Decimal('0.0')
            for line in lines:
                amount += line.debit - line.credit
                if not reconcile_account:
                    reconcile_account = line.account
                if not reconcile_party:
                    reconcile_party = line.party
            if amount:
                move = cls._get_writeoff_move(
                    reconcile_account, reconcile_party, amount,
                    date, writeoff, description)
                move.save()
                lines += cls.search([
                        ('move', '=', move.id),
                        ('account', '=', reconcile_account.id),
                        ('debit', '=', amount < Decimal('0.0') and - amount
                            or Decimal('0.0')),
                        ('credit', '=', amount > Decimal('0.0') and amount
                            or Decimal('0.0')),
                        ], limit=1)
            reconciliations.append({
                    'lines': [('add', [x.id for x in lines])],
                    'date': max(l.date for l in lines),
                    'delegate_to': delegate_to,
                    })
        return Reconciliation.create(reconciliations)

    @classmethod
    def _get_writeoff_move(cls, reconcile_account, reconcile_party, amount,
            date=None, writeoff=None, description=None):
        pool = Pool()
        Date = pool.get('ir.date')
        Period = pool.get('account.period')
        Move = pool.get('account.move')
        if not date:
            date = Date.today()
        period_id = Period.find(reconcile_account.company.id, date=date)
        account = None
        journal = None
        if writeoff:
            if amount >= 0:
                account = writeoff.debit_account
            else:
                account = writeoff.credit_account
            journal = writeoff.journal

        move = Move()
        move.journal = journal
        move.period = period_id
        move.date = date
        move.description = description

        lines = []

        line = cls()
        lines.append(line)
        line.account = reconcile_account
        line.party = reconcile_party
        line.debit = -amount if amount < 0 else 0
        line.credit = amount if amount > 0 else 0

        line = cls()
        lines.append(line)
        line.account = account
        line.party = (
            reconcile_party if account and account.party_required else None)
        line.debit = amount if amount > 0 else 0
        line.credit = -amount if amount < 0 else 0

        move.lines = lines
        return move


class WriteOff(DeactivableMixin, ModelSQL, ModelView):
    'Reconcile Write Off'
    __name__ = 'account.move.reconcile.write_off'
    company = fields.Many2One('company.company', "Company", required=True)
    name = fields.Char("Name", required=True, translate=True)
    journal = fields.Many2One('account.journal', "Journal", required=True,
        domain=[('type', '=', 'write-off')])
    credit_account = fields.Many2One('account.account', "Credit Account",
        required=True,
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('company', '=', Eval('company')),
            ],
        depends=['company'])
    debit_account = fields.Many2One('account.account', "Debit Account",
        required=True,
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('company', '=', Eval('company')),
            ],
        depends=['company'])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('name', 'ASC'))

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')


class OpenJournalAsk(ModelView):
    'Open Journal Ask'
    __name__ = 'account.move.open_journal.ask'
    journal = fields.Many2One('account.journal', 'Journal', required=True)
    period = fields.Many2One('account.period', 'Period', required=True,
        domain=[
            ('state', '!=', 'close'),
            ('fiscalyear.company.id', '=',
                Eval('context', {}).get('company', 0)),
            ])

    @staticmethod
    def default_period():
        Period = Pool().get('account.period')
        return Period.find(Transaction().context.get('company'),
                exception=False)


class OpenJournal(Wizard):
    'Open Journal'
    __name__ = 'account.move.open_journal'
    start = StateTransition()
    ask = StateView('account.move.open_journal.ask',
        'account.open_journal_ask_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Open', 'open_', 'tryton-ok', default=True),
            ])
    open_ = StateAction('account.act_move_line_form')

    def transition_start(self):
        if (Transaction().context.get('active_model', '')
                == 'account.journal.period'
                and Transaction().context.get('active_id')):
            return 'open_'
        return 'ask'

    def default_ask(self, fields):
        JournalPeriod = Pool().get('account.journal.period')
        if (Transaction().context.get('active_model', '') ==
                'account.journal.period'
                and Transaction().context.get('active_id')):
            journal_period = JournalPeriod(Transaction().context['active_id'])
            return {
                'journal': journal_period.journal.id,
                'period': journal_period.period.id,
                }
        return {}

    def do_open_(self, action):
        JournalPeriod = Pool().get('account.journal.period')

        if (Transaction().context.get('active_model', '') ==
                'account.journal.period'
                and Transaction().context.get('active_id')):
            journal_period = JournalPeriod(Transaction().context['active_id'])
            journal = journal_period.journal
            period = journal_period.period
        else:
            journal = self.ask.journal
            period = self.ask.period
        journal_periods = JournalPeriod.search([
                ('journal', '=', journal.id),
                ('period', '=', period.id),
                ], limit=1)
        if not journal_periods:
            journal_period, = JournalPeriod.create([{
                        'journal': journal.id,
                        'period': period.id,
                        }])
        else:
            journal_period, = journal_periods

        action['name'] += ' - %s' % journal_period.rec_name
        action['pyson_domain'] = PYSONEncoder().encode([
            ('journal', '=', journal.id),
            ('period', '=', period.id),
            ])
        action['pyson_context'] = PYSONEncoder().encode({
            'journal': journal.id,
            'period': period.id,
            })
        return action, {}

    def transition_open_(self):
        return 'end'


class OpenAccount(Wizard):
    'Open Account'
    __name__ = 'account.move.open_account'
    start_state = 'open_'
    open_ = StateAction('account.act_move_line_form')

    def do_open_(self, action):
        FiscalYear = Pool().get('account.fiscalyear')

        if not Transaction().context.get('fiscalyear'):
            fiscalyears = FiscalYear.search([
                    ('state', '=', 'open'),
                    ])
        else:
            fiscalyears = [FiscalYear(Transaction().context['fiscalyear'])]

        periods = [p for f in fiscalyears for p in f.periods]

        action['pyson_domain'] = [
            ('period', 'in', [p.id for p in periods]),
            ('account', '=', Transaction().context['active_id']),
            ('state', '=', 'valid'),
            ]
        if Transaction().context.get('posted'):
            action['pyson_domain'].append(('move.state', '=', 'posted'))
        if Transaction().context.get('date'):
            action['pyson_domain'].append(('move.date', '<=',
                    Transaction().context['date']))
        action['pyson_domain'] = PYSONEncoder().encode(action['pyson_domain'])
        action['pyson_context'] = PYSONEncoder().encode({
            'fiscalyear': Transaction().context.get('fiscalyear'),
        })
        return action, {}


class ReconcileLinesWriteOff(ModelView):
    'Reconcile Lines Write-Off'
    __name__ = 'account.move.reconcile_lines.writeoff'
    company = fields.Many2One('company.company', "Company", readonly=True)
    writeoff = fields.Many2One('account.move.reconcile.write_off', "Write Off",
        required=True,
        domain=[
            ('company', '=', Eval('company')),
            ],
        depends=['company'])
    date = fields.Date('Date', required=True)
    amount = fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)),
        readonly=True, depends=['currency_digits'])
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    description = fields.Char('Description')

    @staticmethod
    def default_date():
        Date = Pool().get('ir.date')
        return Date.today()

    @fields.depends('company')
    def on_change_with_currency_digits(self, name=None):
        if self.company:
            return self.company.currency.digits


class ReconcileLines(Wizard):
    'Reconcile Lines'
    __name__ = 'account.move.reconcile_lines'
    start = StateTransition()
    writeoff = StateView('account.move.reconcile_lines.writeoff',
        'account.reconcile_lines_writeoff_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Reconcile', 'reconcile', 'tryton-ok', default=True),
            ])
    reconcile = StateTransition()

    def get_writeoff(self):
        "Return writeoff amount and company"
        Line = Pool().get('account.move.line')

        company = None
        amount = Decimal('0.0')
        for line in Line.browse(Transaction().context['active_ids']):
            amount += line.debit - line.credit
            if not company:
                company = line.account.company
        return amount, company

    def transition_start(self):
        amount, company = self.get_writeoff()
        if not company:
            return 'end'
        if company.currency.is_zero(amount):
            return 'reconcile'
        return 'writeoff'

    def default_writeoff(self, fields):
        amount, company = self.get_writeoff()
        return {
            'amount': amount,
            'company': company.id,
            }

    def transition_reconcile(self):
        Line = Pool().get('account.move.line')

        writeoff = getattr(self.writeoff, 'writeoff', None)
        date = getattr(self.writeoff, 'date', None)
        description = getattr(self.writeoff, 'description', None)
        Line.reconcile(Line.browse(Transaction().context['active_ids']),
            writeoff=writeoff, date=date, description=description)
        return 'end'


class UnreconcileLines(Wizard):
    'Unreconcile Lines'
    __name__ = 'account.move.unreconcile_lines'
    start_state = 'unreconcile'
    unreconcile = StateTransition()

    def transition_unreconcile(self):
        pool = Pool()
        Line = pool.get('account.move.line')
        Reconciliation = pool.get('account.move.reconciliation')

        lines = Line.browse(Transaction().context['active_ids'])
        reconciliations = [x.reconciliation for x in lines if x.reconciliation]
        if reconciliations:
            Reconciliation.delete(reconciliations)
        return 'end'


class Reconcile(Wizard):
    'Reconcile'
    __name__ = 'account.reconcile'
    start_state = 'next_'
    next_ = StateTransition()
    show = StateView('account.reconcile.show',
        'account.reconcile_show_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Skip', 'next_', 'tryton-forward'),
            Button('Reconcile', 'reconcile', 'tryton-ok', default=True),
            ])
    reconcile = StateTransition()

    def get_accounts(self):
        'Return a list of account id to reconcile'
        pool = Pool()
        Rule = pool.get('ir.rule')
        Line = pool.get('account.move.line')
        line = Line.__table__()
        Account = pool.get('account.account')
        AccountType = pool.get('account.account.type')
        account = Account.__table__()
        account_type = AccountType.__table__()
        cursor = Transaction().connection.cursor()
        account_rule = Rule.query_get(Account.__name__)

        context = Transaction().context
        if context['active_model'] == Line.__name__:
            lines = [l for l in Line.browse(context['active_ids'])
                if not l.reconciliation]
            return list({l.account for l in lines if l.account.reconcile})

        balance = line.debit - line.credit
        cursor.execute(*line.join(account,
                condition=line.account == account.id)
            .join(account_type, condition=account.type == account_type.id)
            .select(
                account.id,
                where=((line.reconciliation == Null) & account.reconcile
                    & account.id.in_(account_rule)),
                group_by=[account.id,
                    account_type.receivable, account_type.payable],
                having=((
                        Sum(Case((balance > 0, 1), else_=0)) > 0)
                    & (Sum(Case((balance < 0, 1), else_=0)) > 0)
                    | Case((account_type.receivable & ~account_type.payable,
                            Sum(balance) < 0),
                        else_=False)
                    | Case((account_type.payable & ~account_type.receivable,
                            Sum(balance) > 0),
                        else_=False)
                    )))
        return [a for a, in cursor.fetchall()]

    def get_parties(self, account):
        'Return a list party to reconcile for the account'
        pool = Pool()
        Line = pool.get('account.move.line')
        line = Line.__table__()
        cursor = Transaction().connection.cursor()

        context = Transaction().context
        if context['active_model'] == Line.__name__:
            lines = [l for l in Line.browse(context['active_ids'])
                if not l.reconciliation]
            return list({l.party for l in lines if l.account == account})

        balance = line.debit - line.credit
        cursor.execute(*line.select(line.party,
                where=(line.reconciliation == Null)
                & (line.account == account.id),
                group_by=line.party,
                having=((
                        Sum(Case((balance > 0, 1), else_=0)) > 0)
                    & (Sum(Case((balance < 0, 1), else_=0)) > 0)
                    | Case((account.type.receivable, Sum(balance) < 0),
                        else_=False)
                    | Case((account.type.payable, Sum(balance) > 0),
                        else_=False)
                    )))
        return [p for p, in cursor.fetchall()]

    def transition_next_(self):

        def next_account():
            accounts = list(self.show.accounts)
            if not accounts:
                return
            account = accounts.pop()
            self.show.account = account
            self.show.parties = self.get_parties(account)
            self.show.accounts = accounts
            return account

        def next_party():
            parties = list(self.show.parties)
            if not parties:
                return
            party = parties.pop()
            self.show.party = party
            self.show.parties = parties
            return party

        if getattr(self.show, 'accounts', None) is None:
            self.show.accounts = self.get_accounts()
            if not next_account():
                return 'end'
        if getattr(self.show, 'parties', None) is None:
            self.show.parties = self.get_parties(self.show.account)

        while not next_party():
            if not next_account():
                return 'end'
        return 'show'

    def default_show(self, fields):
        pool = Pool()
        Date = pool.get('ir.date')

        defaults = {}
        defaults['accounts'] = [a.id for a in self.show.accounts]
        defaults['account'] = self.show.account.id
        defaults['parties'] = [p.id for p in self.show.parties]
        defaults['party'] = self.show.party.id if self.show.party else None
        defaults['currency_digits'] = self.show.account.company.currency.digits
        defaults['lines'] = self._default_lines()
        defaults['write_off_amount'] = Decimal(0)
        defaults['date'] = Date.today()
        return defaults

    def _all_lines(self):
        'Return all lines to reconcile for the current state'
        pool = Pool()
        Line = pool.get('account.move.line')
        return Line.search([
                ('account', '=', self.show.account.id),
                ('party', '=',
                    self.show.party.id if self.show.party else None),
                ('reconciliation', '=', None),
                ])

    def _default_lines(self):
        'Return the larger list of lines which can be reconciled'
        pool = Pool()
        Line = pool.get('account.move.line')
        context = Transaction().context
        if context['active_model'] == Line.__name__:
            requested = {l for l in Line.browse(context['active_ids'])
                if l.account == self.show.account
                and l.party == self.show.party}
        else:
            requested = None

        currency = self.show.account.company.currency
        chunk = config.getint('account', 'reconciliation_chunk', default=10)
        # Combination is exponential so it must be limited to small number
        default = []
        for lines in grouped_slice(self._all_lines(), chunk):
            lines = list(lines)
            best = None
            for n in range(len(lines), 1, -1):
                for comb_lines in combinations(lines, n):
                    if requested and not requested.intersection(comb_lines):
                        continue
                    amount = sum((l.debit - l.credit) for l in comb_lines)
                    if currency.is_zero(amount):
                        best = [l.id for l in comb_lines]
                        break
                if best:
                    break
            if best:
                default.extend(best)
        if not default and requested:
            default = list(map(int, requested))
        return default

    def transition_reconcile(self):
        pool = Pool()
        Line = pool.get('account.move.line')

        if self.show.lines:
            Line.reconcile(self.show.lines,
                date=self.show.date,
                writeoff=self.show.write_off,
                description=self.show.description)
        return 'next_'


class ReconcileShow(ModelView):
    'Reconcile'
    __name__ = 'account.reconcile.show'
    accounts = fields.Many2Many('account.account', None, None, 'Account',
        readonly=True)
    account = fields.Many2One('account.account', 'Account', readonly=True)
    parties = fields.Many2Many('party.party', None, None, 'Parties',
        readonly=True)
    party = fields.Many2One('party.party', 'Party', readonly=True)
    lines = fields.Many2Many('account.move.line', None, None, 'Lines',
        domain=[
            ('account', '=', Eval('account')),
            ('party', '=', Eval('party')),
            ('reconciliation', '=', None),
            ],
        depends=['account', 'party'])

    _write_off_states = {
        'required': Bool(Eval('write_off_amount', 0)),
        'invisible': ~Eval('write_off_amount', 0),
        }
    _write_off_depends = ['write_off_amount']

    write_off_amount = fields.Function(fields.Numeric('Amount',
            digits=(16, Eval('currency_digits', 2)),
            states=_write_off_states,
            depends=_write_off_depends + ['currency_digits']),
        'on_change_with_write_off_amount')
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    write_off = fields.Many2One(
        'account.move.reconcile.write_off', "Write Off",
        states=_write_off_states, depends=_write_off_depends)
    date = fields.Date('Date',
        states=_write_off_states, depends=_write_off_depends)
    description = fields.Char('Description',
        states={
            'invisible': _write_off_states['invisible'],
            }, depends=_write_off_depends)

    @fields.depends('lines', 'currency_digits')
    def on_change_with_write_off_amount(self, name=None):
        digits = self.currency_digits or 0
        exp = Decimal(str(10.0 ** -digits))
        amount = sum(((l.debit - l.credit) for l in self.lines), Decimal(0))
        return amount.quantize(exp)

    @fields.depends('account')
    def on_change_with_currency_digits(self, name=None):
        if self.account:
            return self.account.company.currency.digits


class CancelMoves(Wizard):
    'Cancel Moves'
    __name__ = 'account.move.cancel'
    start_state = 'default'
    default = StateView('account.move.cancel.default',
        'account.move_cancel_default_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'cancel', 'tryton-ok', default=True),
            ])
    cancel = StateTransition()

    def default_cancel(self, move):
        default = {}
        if self.default.description:
            default['description'] = self.default.description
        return default

    def transition_cancel(self):
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')

        moves = Move.browse(Transaction().context['active_ids'])
        for move in moves:
            default = self.default_cancel(move)
            cancel_move = move.cancel(default=default)
            to_reconcile = defaultdict(list)
            for line in move.lines + cancel_move.lines:
                if line.account.reconcile:
                    to_reconcile[(line.account, line.party)].append(line)
            for lines in to_reconcile.values():
                Line.reconcile(lines)
        return 'end'


class CancelMovesDefault(ModelView):
    'Cancel Moves'
    __name__ = 'account.move.cancel.default'
    description = fields.Char('Description')


class GroupLines(Wizard):
    "Group Lines"
    __name__ = 'account.move.line.group'
    start = StateView('account.move.line.group.start',
        'account.move_line_group_start_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Group", 'group', 'tryton-ok', default=True),
            ])
    group = StateTransition()

    def transition_group(self):
        pool = Pool()
        Line = pool.get('account.move.line')

        lines = Line.browse(Transaction().context['active_ids'])
        grouping = self.grouping(lines)

        move, balance_line = self.get_move(lines, grouping)
        move.save()

        to_reconcile = defaultdict(list)
        for line in chain(lines, move.lines):
            if line.account.reconcile:
                to_reconcile[line.account].append(line)

        if balance_line:
            balance_line.move = move
            balance_line.save()

        for lines in to_reconcile.values():
            Line.reconcile(lines, delegate_to=balance_line)

        return 'end'

    @classmethod
    def grouping(cls, lines):
        if len(lines) == 1:
            raise GroupLineError(gettext('account.msg_group_line_single'))
        companies = set()
        parties = set()
        accounts = set()
        second_currencies = set()
        for line in lines:
            if not cls.allow_grouping(line.account):
                raise GroupLineError(gettext('account.msg_group_line'))
            companies.add(line.move.company)
            parties.add(line.party)
            accounts.add(line.account)
            second_currencies.add(line.second_currency)
        try:
            company, = companies
        except ValueError:
            raise GroupLineError(
                gettext('account.msg_group_line_same_company'))
        try:
            party, = parties
        except ValueError:
            raise GroupLineError(
                gettext('account.msg_group_line_many_parties'))
        try:
            second_currency, = second_currencies
        except ValueError:
            raise GroupLineError(
                gettext('account.msg_group_line_same_second_currency'))
        if len(accounts) > 2:
            raise GroupLineError(
                gettext('account.msg_group_line_maximum_account'))
        return {
            'company': company,
            'party': party,
            'second_currency': second_currency,
            'accounts': accounts,
            }

    @classmethod
    def allow_grouping(cls, account):
        return account.type.payable or account.type.receivable

    def get_move(self, lines, grouping, date=None):
        pool = Pool()
        Date = pool.get('ir.date')
        Move = pool.get('account.move')
        Period = pool.get('account.period')
        Line = pool.get('account.move.line')

        if not date:
            date = Date.today()
        period = Period.find(grouping['company'].id, date=date)

        move = Move()
        move.date = date
        move.period = period
        move.journal = self.start.journal
        move.description = self.start.description

        accounts = {a: 0 for a in grouping['accounts']}
        amount_second_currency = 0
        maturity_dates = {a: None for a in grouping['accounts']}

        counterpart_lines = []
        for line in lines:
            if maturity_dates[line.account] and line.maturity_date:
                maturity_dates[line.account] = min(
                    maturity_dates[line.account], line.maturity_date)
            elif line.maturity_date:
                maturity_dates[line.account] = line.maturity_date
            cline = self._counterpart_line(line)
            accounts[cline.account] += cline.debit - cline.credit
            if cline.amount_second_currency:
                amount_second_currency += cline.amount_second_currency
            counterpart_lines.append(cline)
        move.lines = counterpart_lines

        balance_line = None
        if len(accounts) == 1:
            account, = grouping['accounts']
            amount = -accounts[account]
            if amount:
                balance_line = Line()
                balance_line.account = account
        else:
            first, second = grouping['accounts']
            if accounts[first] != accounts[second]:
                balance_line = Line()
                amount = -(accounts[first] + accounts[second])
                if abs(accounts[first]) > abs(accounts[second]):
                    balance_line.account = first
                else:
                    balance_line.account = second
        if balance_line:
            if balance_line.account.party_required:
                balance_line.party = grouping['party']
            if amount > 0:
                balance_line.debit, balance_line.credit = amount, 0
            else:
                balance_line.debit, balance_line.credit = 0, -amount
            if grouping['second_currency']:
                balance_line.second_currency = grouping['second_currency']
                balance_line.amount_second_currency = (
                    -amount_second_currency)
            balance_line.maturity_date = maturity_dates[balance_line.account]
        return move, balance_line

    def _counterpart_line(self, line):
        pool = Pool()
        Line = pool.get('account.move.line')

        counterpart = Line()
        counterpart.account = line.account
        counterpart.debit = line.credit
        counterpart.credit = line.debit
        counterpart.party = line.party
        counterpart.second_currency = line.second_currency
        if line.second_currency:
            counterpart.amount_second_currency = -line.amount_second_currency
        else:
            counterpart.amount_second_currency = None
        return counterpart


class GroupLinesStart(ModelView):
    "Group Lines"
    __name__ = 'account.move.line.group.start'

    journal = fields.Many2One('account.journal', "Journal", required=True)
    description = fields.Char("Description")


class PrintGeneralJournalStart(ModelView):
    'Print General Journal'
    __name__ = 'account.move.print_general_journal.start'
    from_date = fields.Date('From Date', required=True)
    to_date = fields.Date('To Date', required=True)
    company = fields.Many2One('company.company', 'Company', required=True)
    posted = fields.Boolean('Posted Move', help='Show only posted move')

    @staticmethod
    def default_from_date():
        Date = Pool().get('ir.date')
        return datetime.date(Date.today().year, 1, 1)

    @staticmethod
    def default_to_date():
        Date = Pool().get('ir.date')
        return Date.today()

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_posted():
        return False


class PrintGeneralJournal(Wizard):
    'Print General Journal'
    __name__ = 'account.move.print_general_journal'
    start = StateView('account.move.print_general_journal.start',
        'account.print_general_journal_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateReport('account.move.general_journal')

    def do_print_(self, action):
        data = {
            'company': self.start.company.id,
            'from_date': self.start.from_date,
            'to_date': self.start.to_date,
            'posted': self.start.posted,
            }
        return action, data


class GeneralJournal(Report):
    __name__ = 'account.move.general_journal'

    @classmethod
    def _get_records(cls, ids, model, data):
        Move = Pool().get('account.move')

        clause = [
            ('date', '>=', data['from_date']),
            ('date', '<=', data['to_date']),
            ('period.fiscalyear.company', '=', data['company']),
            ]
        if data['posted']:
            clause.append(('state', '=', 'posted'))
        return Move.search(clause,
                order=[('date', 'ASC'), ('id', 'ASC')])

    @classmethod
    def get_context(cls, records, data):
        report_context = super(GeneralJournal, cls).get_context(records, data)

        Company = Pool().get('company.company')

        company = Company(data['company'])

        report_context['company'] = company
        report_context['digits'] = company.currency.digits
        report_context['from_date'] = data['from_date']
        report_context['to_date'] = data['to_date']

        return report_context
