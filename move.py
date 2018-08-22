# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
import datetime
from itertools import groupby, combinations
from operator import itemgetter
from collections import defaultdict

from sql import Null
from sql.aggregate import Sum, Max
from sql.conditionals import Coalesce, Case

from trytond.model import ModelView, ModelSQL, fields, Check
from trytond.wizard import Wizard, StateTransition, StateView, StateAction, \
    StateReport, Button
from trytond.report import Report
from trytond import backend
from trytond.pyson import Eval, Bool, If, PYSONEncoder
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.rpc import RPC
from trytond.tools import reduce_ids, grouped_slice
from trytond.config import config

__all__ = ['Move', 'Reconciliation', 'Line', 'OpenJournalAsk',
    'OpenJournal', 'OpenAccount',
    'ReconcileLinesWriteOff', 'ReconcileLines',
    'UnreconcileLines',
    'Reconcile', 'ReconcileShow',
    'CancelMoves', 'CancelMovesDefault',
    'FiscalYearLine', 'FiscalYear2',
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
            ],
        states=_MOVE_STATES, depends=_MOVE_DEPENDS + ['company'], select=True)
    journal = fields.Many2One('account.journal', 'Journal', required=True,
            states=_MOVE_STATES, depends=_MOVE_DEPENDS)
    date = fields.Date('Effective Date', required=True, states=_MOVE_STATES,
        depends=_MOVE_DEPENDS)
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
        cls._error_messages.update({
                'post_empty_move': ('You can not post move "%s" because it is '
                    'empty.'),
                'post_unbalanced_move': ('You can not post move "%s" because '
                    'it is an unbalanced.'),
                'modify_posted_move': ('You can not modify move "%s" because '
                    'it is already posted.'),
                'date_outside_period': ('You can not create move "%(move)s" '
                    'because its date is outside its period.'),
                'period_cancel': (
                    'The period of move "%s" is closed.\n'
                    'Use the current period?'),
                })
        cls._buttons.update({
                'post': {
                    'invisible': Eval('state') == 'posted',
                    },
                })

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        table = TableHandler(cls, module_name)
        sql_table = cls.__table__()
        pool = Pool()
        Period = pool.get('account.period')
        period = Period.__table__()
        FiscalYear = pool.get('account.fiscalyear')
        fiscalyear = FiscalYear.__table__()

        # Migration from 2.4:
        #   - name renamed into number
        #   - reference renamed into post_number
        if table.column_exist('name'):
            table.column_rename('name', 'number')
        if table.column_exist('reference'):
            table.column_rename('reference', 'post_number')

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

        table = TableHandler(cls, module_name)
        table.index_action(['journal', 'period'], 'add')

        # Add index on create_date
        table.index_action('create_date', action='add')

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
        period_id = cls.default_period()
        if period_id:
            period = Period(period_id)
            return period.start_date
        return Date.today()

    @fields.depends('period', 'journal', 'date')
    def on_change_with_date(self):
        Line = Pool().get('account.move.line')
        date = self.date
        if date:
            if self.period and not (
                    self.period.start_date <= date <= self.period.end_date):
                date = self.period.start_date
            return date
        lines = Line.search([
                ('journal', '=', self.journal),
                ('period', '=', self.period),
                ], order=[('id', 'DESC')], limit=1)
        if lines:
            date = lines[0].date
        elif self.period:
            date = self.period.start_date
        return date

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
            self.raise_user_error('date_outside_period', {
                        'move': self.rec_name,
                        })

    @classmethod
    def check_modify(cls, moves):
        'Check posted moves for modifications.'
        for move in moves:
            if move.state == 'posted':
                cls.raise_user_error('modify_posted_move', (move.rec_name,))

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
            keys = values.keys()
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
        Line = Pool().get('account.move.line')

        if default is None:
            default = {}
        default = default.copy()
        default['number'] = None
        default['post_number'] = None
        default['state'] = cls.default_state()
        default['post_date'] = None
        default['lines'] = None

        new_moves = []
        for move in moves:
            new_move, = super(Move, cls).copy([move], default=default)
            Line.copy(move.lines, default={
                    'move': new_move.id,
                    })
            new_moves.append(new_move)
        return new_moves

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

        default = {
            'origin': str(self),
            }
        if self.period.state == 'close':
            self.raise_user_warning('%s.cancel' % self,
                'period_cancel', self.rec_name)
            date = Date.today()
            period_id = Period.find(self.company.id, date=date)
            default.update({
                    'date': date,
                    'period': period_id,
                    })
        return default

    def cancel(self, default=None):
        'Return a cancel move'
        if default is None:
            default = {}
        default.update(self._cancel_default())
        cancel_move, = self.copy([self], default=default)
        for line in cancel_move.lines:
            line.debit *= -1
            line.credit *= -1
            if line.second_currency:
                line.amount_second_currency *= -1
            for tax_line in line.tax_lines:
                tax_line.amount *= -1
            line.tax_lines = line.tax_lines  # Force tax_lines changing
        cancel_move.lines = cancel_move.lines  # Force lines changing
        cancel_move.save()
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
                cls.raise_user_error('post_empty_move', (move.rec_name,))
            company = None
            for line in move.lines:
                amount += line.debit - line.credit
                if not company:
                    company = line.account.company
            if not company.currency.is_zero(amount):
                cls.raise_user_error('post_unbalanced_move', (move.rec_name,))
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

    @classmethod
    def __setup__(cls):
        super(Reconciliation, cls).__setup__()
        cls._error_messages.update({
                'modify': 'You can not modify a reconciliation.',
                'reconciliation_line_not_valid': ('You can not reconcile line '
                    '"%s" because it is not in valid state.'),
                'reconciliation_different_accounts': ('You can not reconcile '
                    'line "%(line)s" because its account "%(account1)s" is '
                    'different from "%(account2)s".'),
                'reconciliation_account_no_reconcile': (
                    'You can not reconcile '
                    'line "%(line)s" because its account "%(account)s" is '
                    'configured as not reconcilable.'),
                'reconciliation_different_parties': ('You can not reconcile '
                    'line "%(line)s" because its party "%(party1)s" is '
                    'different from "%(party2)s".'),
                'reconciliation_unbalanced': ('You can not create a '
                    'reconciliation where debit "%(debit)s" and credit '
                    '"%(credit)s" differ.'),
                })

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        table = TableHandler(cls, module_name)
        sql_table = cls.__table__()
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        move = Move.__table__()
        line = Line.__table__()

        date_exist = table.column_exist('date')

        super(Reconciliation, cls).__register__(module_name)

        # Migration from 3.8: new date field
        if not date_exist and TableHandler.table_exist(Line._table):
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
        cls.raise_user_error('modify')

    @classmethod
    def validate(cls, reconciliations):
        super(Reconciliation, cls).validate(reconciliations)
        cls.check_lines(reconciliations)

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
                    cls.raise_user_error('reconciliation_line_not_valid',
                        (line.rec_name,))
                debit += line.debit
                credit += line.credit
                if not account:
                    account = line.account
                elif account.id != line.account.id:
                    cls.raise_user_error('reconciliation_different_accounts', {
                            'line': line.rec_name,
                            'account1': line.account.rec_name,
                            'account2': account.rec_name,
                            })
                if not account.reconcile:
                    cls.raise_user_error('reconciliation_account_no_reconcile',
                        {
                            'line': line.rec_name,
                            'account': line.account.rec_name,
                            })
                if line.party != party:
                    cls.raise_user_error('reconciliation_different_parties', {
                            'line': line.rec_name,
                            'party1': line.party.rec_name,
                            'party2': party.rec_name,
                            })
            if not account.company.currency.is_zero(debit - credit):
                language = Transaction().language
                languages = Lang.search([('code', '=', language)])
                if not languages:
                    languages = Lang.search([('code', '=', 'en')])
                language = languages[0]
                debit = Lang.currency(
                    language, debit, account.company.currency)
                credit = Lang.currency(
                    language, credit, account.company.currency)
                cls.raise_user_error('reconciliation_unbalanced', {
                        'debit': debit,
                        'credit': credit,
                        })


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
            domain=[('kind', '!=', 'view')],
            select=True, states=_states, depends=_depends)
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
            'get_move_field', setter='set_move_field',
            searcher='search_move_field')
    origin = fields.Function(fields.Reference('Origin',
            selection='get_origin'),
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
        states=_states, depends=_depends,
        help='This field is used for payable and receivable lines. \n'
        'You can put the limit date for the payment.')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('valid', 'Valid'),
        ], 'State', readonly=True, required=True, select=True)
    reconciliation = fields.Many2One('account.move.reconciliation',
            'Reconciliation', readonly=True, ondelete='SET NULL', select=True)
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
        cls._check_modify_exclude = {'reconciliation'}
        cls._reconciliation_modify_disallow = {
            'account', 'debit', 'credit', 'party',
            }
        table = cls.__table__()
        cls._sql_constraints += [
            ('credit_debit',
                Check(table, table.credit * table.debit == 0),
                'Wrong credit/debit values.'),
            ('second_currency_sign',
                Check(table, Coalesce(table.amount_second_currency, 0)
                    * (table.debit - table.credit) >= 0),
                'wrong_second_currency_sign'),
            ]
        cls.__rpc__.update({
                'on_write': RPC(instantiate=0),
                'get_origin': RPC(),
                })
        cls._order[0] = ('id', 'DESC')
        cls._error_messages.update({
                'add_modify_closed_journal_period': ('You can not '
                    'add/modify lines in closed journal period "%s".'),
                'modify_posted_move': ('You can not modify lines of move "%s" '
                    'because it is already posted.'),
                'modify_reconciled': ('You can not modify line "%s" because '
                    'it is reconciled.'),
                'no_journal': ('Move line cannot be created because there is '
                    'no journal defined.'),
                'move_view_account': ('You can not create a move line with '
                    'account "%s" because it is a view account.'),
                'move_inactive_account': ('You can not create a move line '
                    'with account "%s" because it is inactive.'),
                'already_reconciled': 'Line "%s" (%d) already reconciled.',
                'party_required': 'Party is required on line "%s"',
                'party_set': 'Party must not be set on line "%s"',
                'wrong_second_currency_sign': 'Wrong second currency sign.',
                })

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        table = TableHandler(cls, module_name)

        # Migration from 2.4: reference renamed into description
        if table.column_exist('reference'):
            table.column_rename('reference', 'description')

        super(Line, cls).__register__(module_name)

        table = TableHandler(cls, module_name)
        # Index for General Ledger
        table.index_action(['move', 'account'], 'add')

        # Migration from 1.2
        table.not_null_action('blocked', action='remove')

        # Migration from 2.4: remove name, active
        table.not_null_action('name', action='remove')
        table.not_null_action('active', action='remove')
        table.index_action('active', action='remove')

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

    @classmethod
    def default_get(cls, fields, with_rec_name=True):
        pool = Pool()
        Move = pool.get('account.move')
        Tax = pool.get('account.tax')
        Account = pool.get('account.account')
        TaxCode = pool.get('account.tax.code')
        values = super(Line, cls).default_get(fields,
                with_rec_name=with_rec_name)

        if 'move' not in fields:
            # Not manual entry
            if 'date' in values:
                values = values.copy()
                del values['date']
            return values

        if (Transaction().context.get('journal')
                and Transaction().context.get('period')):
            lines = cls.search([
                ('move.journal', '=', Transaction().context['journal']),
                ('move.period', '=', Transaction().context['period']),
                ('create_uid', '=', Transaction().user),
                ('state', '=', 'draft'),
                ], order=[('id', 'DESC')], limit=1)
            if not lines:
                return values
            move = lines[0].move
            values['move'] = move.id
            values['move.rec_name'] = move.rec_name

        if 'move' not in values:
            return values

        move = Move(values['move'])
        total = Decimal('0.0')
        taxes = {}
        no_code_taxes = []
        for line in move.lines:
            total += line.debit - line.credit
            if line.party and 'party' in fields and 'party' not in values:
                values['party'] = line.party.id
                values['party.rec_name'] = line.party.rec_name
            if move.journal.type in ('expense', 'revenue'):
                line_code_taxes = [x.code.id for x in line.tax_lines]
                for tax in line.account.taxes:
                    if move.journal.type == 'revenue':
                        if line.debit:
                            base_id = (tax.credit_note_base_code.id
                                if tax.credit_note_base_code else None)
                            code_id = (tax.credit_note_tax_code.id
                                if tax.credit_note_tax_code else None)
                            account_id = (tax.credit_note_account.id
                                if tax.credit_note_account else None)
                        else:
                            base_id = (tax.invoice_base_code.id
                                if tax.invoice_base_code else None)
                            code_id = (tax.invoice_tax_code.id
                                if tax.invoice_tax_code else None)
                            account_id = (tax.invoice_account.id
                                if tax.invoice_account else None)
                    else:
                        if line.debit:
                            base_id = (tax.invoice_base_code.id
                                if tax.invoice_base_code else None)
                            code_id = (tax.invoice_tax_code.id
                                if tax.invoice_tax_code else None)
                            account_id = (tax.invoice_account.id
                                if tax.invoice_account else None)
                        else:
                            base_id = (tax.credit_note_base_code.id
                                if tax.credit_note_base_code else None)
                            code_id = (tax.credit_note_tax_code.id
                                if tax.credit_note_tax_code else None)
                            account_id = (tax.credit_note_account.id
                                if tax.credit_note_account else None)
                    if base_id in line_code_taxes or not base_id:
                        taxes.setdefault((account_id, code_id, tax.id), None)
                for tax_line in line.tax_lines:
                    taxes[
                        (line.account.id, tax_line.code.id, tax_line.tax.id)
                        ] = True
                if not line.tax_lines:
                    no_code_taxes.append(line.account.id)
        for no_code_account_id in no_code_taxes:
            for (account_id, code_id, tax_id), test in \
                    taxes.iteritems():
                if (not test
                        and not code_id
                        and no_code_account_id == account_id):
                    taxes[(account_id, code_id, tax_id)] = True

        if 'account' in fields:
            account = None
            if total >= Decimal('0.0'):
                if move.journal.credit_account:
                    account = move.journal.credit_account
            else:
                if move.journal.debit_account:
                    account = move.journal.debit_account
            if account:
                    values['account'] = account.id
                    values['account.rec_name'] = account.rec_name
            else:
                values['account'] = None

        if ('debit' in fields) or ('credit' in fields):
            values['debit'] = total < 0 and - total or Decimal(0)
            values['credit'] = total > 0 and total or Decimal(0)

        if move.journal.type in ('expense', 'revenue'):
            for account_id, code_id, tax_id in taxes:
                if taxes[(account_id, code_id, tax_id)]:
                    continue
                for line in move.lines:
                    if move.journal.type == 'revenue':
                        if line.debit:
                            key = 'credit_note'
                        else:
                            key = 'invoice'
                    else:
                        if line.debit:
                            key = 'invoice'
                        else:
                            key = 'credit_note'
                    line_amount = Decimal('0.0')
                    tax_amount = Decimal('0.0')
                    for tax_line in Tax.compute(line.account.taxes,
                            line.debit or line.credit, 1):
                        tax_account = getattr(tax_line['tax'],
                            key + '_account')
                        tax_code = getattr(tax_line['tax'], key + '_tax_code')
                        if ((tax_account.id if tax_account
                                    else line.account.id) == account_id
                                and (tax_code.id if tax_code else None
                                    == code_id)
                                and tax_line['tax'].id == tax_id):
                            if line.debit:
                                line_amount += tax_line['amount']
                            else:
                                line_amount -= tax_line['amount']
                            tax_amount += tax_line['amount'] * \
                                getattr(tax_line['tax'], key + '_tax_sign')
                    line_amount = line.account.company.currency.round(
                        line_amount)
                    tax_amount = line.account.company.currency.round(
                        tax_amount)
                    if ('debit' in fields):
                        values['debit'] = line_amount > Decimal('0.0') \
                            and line_amount or Decimal('0.0')
                    if ('credit' in fields):
                        values['credit'] = line_amount < Decimal('0.0') \
                            and - line_amount or Decimal('0.0')
                    if 'account' in fields and account_id:
                        values['account'] = account_id
                        values['account.rec_name'] = Account(
                            account_id).rec_name
                    if 'tax_lines' in fields and code_id:
                        values['tax_lines'] = [
                            {
                                'amount': tax_amount,
                                'currency_digits': line.currency_digits,
                                'code': code_id,
                                'code.rec_name': TaxCode(code_id).rec_name,
                                'tax': tax_id,
                                'tax.rec_name': Tax(tax_id).rec_name,
                            },
                        ]
        return values

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
    def get_origin(cls):
        Move = Pool().get('account.move')
        return Move.get_origin()

    @fields.depends('account', 'debit', 'credit', 'tax_lines', 'journal',
        'move', 'amount_second_currency')
    def on_change_debit(self):
        Journal = Pool().get('account.journal')
        if self.journal or Transaction().context.get('journal'):
            journal = self.journal or Journal(Transaction().context['journal'])
            if journal.type in ('expense', 'revenue'):
                self._compute_tax_lines(journal.type)
        if self.debit:
            self.credit = Decimal('0.0')
        self._amount_second_currency_sign()

    @fields.depends('account', 'debit', 'credit', 'tax_lines', 'journal',
        'move', 'amount_second_currency')
    def on_change_credit(self):
        Journal = Pool().get('account.journal')
        if self.journal or Transaction().context.get('journal'):
            journal = self.journal or Journal(Transaction().context['journal'])
            if journal.type in ('expense', 'revenue'):
                self._compute_tax_lines(journal.type)
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

    @fields.depends('account', 'debit', 'credit', 'tax_lines', 'journal',
        'move')
    def on_change_account(self):
        Journal = Pool().get('account.journal')

        if Transaction().context.get('journal'):
            journal = Journal(Transaction().context['journal'])
            if journal.type in ('expense', 'revenue'):
                self._compute_tax_lines(journal.type)

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

    def _compute_tax_lines(self, journal_type):
        pool = Pool()
        Tax = pool.get('account.tax')
        TaxLine = pool.get('account.tax.line')

        if self.move:
            # Only for first line
            return
        tax_lines = []
        if self.account:
            debit = self.debit or Decimal('0.0')
            credit = self.credit or Decimal('0.0')
            for tax in self.account.taxes:
                if journal_type == 'revenue':
                    if debit:
                        key = 'credit_note'
                    else:
                        key = 'invoice'
                else:
                    if debit:
                        key = 'invoice'
                    else:
                        key = 'credit_note'
                base_amounts = {}
                for tax_line in Tax.compute(self.account.taxes,
                        debit or credit, 1):
                    code = getattr(tax_line['tax'], key + '_base_code')
                    code_id = code.id if code else None
                    if not code_id:
                        continue
                    tax_id = tax_line['tax'].id
                    base_amounts.setdefault((code_id, tax_id), Decimal('0.0'))
                    base_amounts[code_id, tax_id] += tax_line['base'] * \
                        getattr(tax_line['tax'], key + '_tax_sign')
                for code_id, tax_id in base_amounts:
                    if not base_amounts[code_id, tax_id]:
                        continue
                    tax_line = TaxLine(**TaxLine.default_get(
                            TaxLine._fields.keys()))

                    tax_line.amount = base_amounts[code_id, tax_id]
                    tax_line.currency_digits = self.account.currency_digits
                    tax_line.code = code_id
                    tax_line.tax = tax_id
                    tax_lines.append(tax_line)
        self.tax_lines = tax_lines

    @fields.depends('move', 'party', 'account', 'debit', 'credit', 'journal')
    def on_change_party(self):
        Journal = Pool().get('account.journal')
        cursor = Transaction().connection.cursor()
        if (not self.party) or self.account:
            return

        if not self.party.account_receivable \
                or not self.party.account_payable:
            return

        if self.party and (not self.debit) and (not self.credit):
            type_name = self.__class__.debit.sql_type().base
            table = self.__table__()
            column = Coalesce(Sum(Coalesce(table.debit, 0)
                    - Coalesce(table.credit, 0)), 0).cast(type_name)
            where = ((table.reconciliation == Null)
                & (table.party == self.party.id))
            cursor.execute(*table.select(column,
                    where=where
                    & (table.account == self.party.account_receivable.id)))
            amount = cursor.fetchone()[0]
            # SQLite uses float for SUM
            if not isinstance(amount, Decimal):
                amount = Decimal(str(amount))
            if not self.party.account_receivable.currency.is_zero(amount):
                if amount > Decimal('0.0'):
                    self.credit = \
                        self.party.account_receivable.currency.round(amount)
                    self.debit = Decimal('0.0')
                else:
                    self.credit = Decimal('0.0')
                    self.debit = \
                        - self.party.account_receivable.currency.round(amount)
                self.account = self.party.account_receivable
            else:
                cursor.execute(*table.select(column,
                        where=where
                        & (table.account == self.party.account_payable.id)))
                amount = cursor.fetchone()[0]
                # SQLite uses float for SUM
                if not isinstance(amount, Decimal):
                    amount = Decimal(str(amount))
                if not self.party.account_payable.currency.is_zero(amount):
                    if amount > Decimal('0.0'):
                        self.credit = \
                            self.party.account_payable.currency.round(amount)
                        self.debit = Decimal('0.0')
                    else:
                        self.credit = Decimal('0.0')
                        self.debit = \
                            - self.party.account_payable.currency.round(amount)
                    self.account = self.party.account_payable

        if self.party and self.debit:
            if self.debit > Decimal('0.0'):
                if not self.account:
                    self.account = self.party.account_receivable
            else:
                if not self.account:
                    self.account = self.party.account_payable

        if self.party and self.credit:
            if self.credit > Decimal('0.0'):
                if not self.account:
                    self.account = self.party.account_payable
            else:
                if not self.account:
                    self.account = self.party.account_receivable

        journal = None
        if self.journal:
            journal = self.journal
        elif Transaction().context.get('journal'):
            journal = Journal(Transaction().context.get('journal'))
        if journal and self.party:
            if journal.type == 'revenue':
                if not self.account:
                    self.account = self.party.account_receivable
            elif journal.type == 'expense':
                if not self.account:
                    self.account = self.party.account_payable

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

    @fields.depends('move','_parent_move.state')
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
    order_origin = _order_move_field('origin')
    order_move_state = _order_move_field('state')

    def get_amount(self, name):
        sign = 1 if self.account.type.display_balance == 'debit-credit' else -1
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

        if Transaction().context.get('date'):
            fiscalyears = FiscalYear.search([
                    ('start_date', '<=', Transaction().context['date']),
                    ('end_date', '>=', Transaction().context['date']),
                    ('company', '=', Transaction().context.get('company')),
                    ], limit=1)

            fiscalyear_id = fiscalyears and fiscalyears[0].id or 0

            if Transaction().context.get('posted'):
                return ((table.state != 'draft')
                    & table.move.in_(move.join(period,
                            condition=move.period == period.id
                            ).select(move.id,
                            where=(period.fiscalyear == fiscalyear_id)
                            & (move.date <= Transaction().context['date'])
                            & (move.state == 'posted'))),
                    [f.id for f in fiscalyears])
            else:
                return ((table.state != 'draft')
                    & table.move.in_(move.join(period,
                            condition=move.period == period.id
                            ).select(move.id,
                            where=(period.fiscalyear == fiscalyear_id)
                            & (move.date <= Transaction().context['date']))),
                    [f.id for f in fiscalyears])

        if Transaction().context.get('periods'):
            if Transaction().context.get('fiscalyear'):
                fiscalyear_ids = [Transaction().context['fiscalyear']]
            else:
                fiscalyear_ids = []
            if Transaction().context.get('posted'):
                return ((table.state != 'draft')
                    & table.move.in_(
                            move.select(move.id,
                                where=move.period.in_(
                                    Transaction().context['periods'])
                                & (move.state == 'posted'))),
                    fiscalyear_ids)
            else:
                return ((table.state != 'draft')
                    & table.move.in_(
                        move.select(move.id,
                            where=move.period.in_(
                                Transaction().context['periods']))),
                    fiscalyear_ids)
        else:
            if not Transaction().context.get('fiscalyear'):
                fiscalyears = FiscalYear.search([
                    ('state', '=', 'open'),
                    ('company', '=', Transaction().context.get('company')),
                    ])
                fiscalyear_ids = [f.id for f in fiscalyears] or [0]
            else:
                fiscalyear_ids = [Transaction().context.get('fiscalyear')]

            if Transaction().context.get('posted'):
                return ((table.state != 'draft')
                    & table.move.in_(
                        move.select(move.id,
                            where=move.period.in_(
                                period.select(period.id,
                                    where=period.fiscalyear.in_(
                                        fiscalyear_ids)))
                            & (move.state == 'posted'))),
                    fiscalyear_ids)
            else:
                return ((table.state != 'draft')
                    & table.move.in_(
                        move.select(move.id,
                            where=move.period.in_(
                                period.select(period.id,
                                    where=period.fiscalyear.in_(
                                        fiscalyear_ids))))),
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
        if self.account.kind in ('view',):
            self.raise_user_error('move_view_account', (
                    self.account.rec_name,))
        if not self.account.active:
            self.raise_user_error('move_inactive_account', (
                    self.account.rec_name,))
        if bool(self.party) != bool(self.account.party_required):
            error = 'party_set' if self.party else 'party_required'
            self.raise_user_error(error, self.rec_name)

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
                cls.raise_user_error('add_modify_closed_journal_period', (
                        journal_period.rec_name,))
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
                cls.raise_user_error('modify_posted_move', (
                        line.move.rec_name,))
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
                cls.raise_user_error('modify_reconciled', line.rec_name)

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
                journal_id = (vals.get('journal')
                        or Transaction().context.get('journal'))
                if not journal_id:
                    cls.raise_user_error('no_journal')
                if move is None:
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
        if 'move' not in default:
            default['move'] = None
        if 'reconciliation' not in default:
            default['reconciliation'] = None
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
    def reconcile(cls, lines, journal=None, date=None, account=None,
            description=None):
        pool = Pool()
        Move = pool.get('account.move')
        Reconciliation = pool.get('account.move.reconciliation')
        Period = pool.get('account.period')
        Date = pool.get('ir.date')

        for line in lines:
            if line.reconciliation:
                cls.raise_user_error('already_reconciled',
                        error_args=(line.move.number, line.id,))

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
        amount = reconcile_account.currency.round(amount)
        if not account and journal:
            if amount >= 0:
                account = journal.debit_account
            else:
                account = journal.credit_account
        if journal and account:
            if not date:
                date = Date.today()
            period_id = Period.find(reconcile_account.company.id, date=date)
            move, = Move.create([{
                        'journal': journal.id,
                        'period': period_id,
                        'date': date,
                        'description': description,
                        'lines': [
                            ('create', [{
                                        'account': reconcile_account.id,
                                        'party': (reconcile_party.id
                                            if reconcile_party else None),
                                        'debit': (amount < Decimal('0.0')
                                            and - amount or Decimal('0.0')),
                                        'credit': (amount > Decimal('0.0')
                                            and amount or Decimal('0.0')),
                                        }, {
                                        'account': account.id,
                                        'party': (reconcile_party.id
                                            if (account.party_required and
                                                reconcile_party)
                                            else None),
                                        'debit': (amount > Decimal('0.0')
                                            and amount or Decimal('0.0')),
                                        'credit': (amount < Decimal('0.0')
                                            and - amount or Decimal('0.0')),
                                        }]),
                            ],
                        }])
            lines += cls.search([
                    ('move', '=', move.id),
                    ('account', '=', reconcile_account.id),
                    ('debit', '=', amount < Decimal('0.0') and - amount
                        or Decimal('0.0')),
                    ('credit', '=', amount > Decimal('0.0') and amount
                        or Decimal('0.0')),
                    ], limit=1)
        return Reconciliation.create([{
                    'lines': [('add', [x.id for x in lines])],
                    'date': max(l.date for l in lines),
                    }])[0]


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
    journal = fields.Many2One('account.journal', 'Journal', required=True,
        domain=[
            ('type', '=', 'write-off'),
            ])
    date = fields.Date('Date', required=True)
    amount = fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)),
        readonly=True, depends=['currency_digits'])
    currency_digits = fields.Integer('Currency Digits', readonly=True)
    description = fields.Char('Description')

    @staticmethod
    def default_date():
        Date = Pool().get('ir.date')
        return Date.today()


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
            'currency_digits': company.currency.digits,
            }

    def transition_reconcile(self):
        Line = Pool().get('account.move.line')

        journal = getattr(self.writeoff, 'journal', None)
        date = getattr(self.writeoff, 'date', None)
        description = getattr(self.writeoff, 'description', None)
        Line.reconcile(Line.browse(Transaction().context['active_ids']),
            journal=journal, date=date, description=description)
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
            Button('Skip', 'next_', 'tryton-go-next'),
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
        account = Account.__table__()
        cursor = Transaction().connection.cursor()
        account_rule = Rule.query_get(Account.__name__)

        balance = line.debit - line.credit
        cursor.execute(*line.join(account,
                condition=line.account == account.id).select(
                account.id,
                where=((line.reconciliation == Null) & account.reconcile
                    & account.id.in_(account_rule)),
                group_by=account.id,
                having=(
                    Sum(Case((balance > 0, 1), else_=0)) > 0)
                & (Sum(Case((balance < 0, 1), else_=0)) > 0)
                ))
        return [a for a, in cursor.fetchall()]

    def get_parties(self, account):
        'Return a list party to reconcile for the account'
        pool = Pool()
        Line = pool.get('account.move.line')
        line = Line.__table__()
        cursor = Transaction().connection.cursor()

        balance = line.debit - line.credit
        cursor.execute(*line.select(line.party,
                where=(line.reconciliation == Null)
                & (line.account == account.id),
                group_by=line.party,
                having=(
                    Sum(Case((balance > 0, 1), else_=0)) > 0)
                & (Sum(Case((balance < 0, 1), else_=0)) > 0)
                ))
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
        defaults['write_off'] = Decimal(0)
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
        currency = self.show.account.company.currency
        chunk = config.getint('account', 'reconciliation_chunk', default=10)
        # Combination is exponential so it must be limited to small number
        default = []
        for lines in grouped_slice(self._all_lines(), chunk):
            lines = list(lines)
            best = None
            for n in xrange(len(lines), 1, -1):
                for comb_lines in combinations(lines, n):
                    amount = sum((l.debit - l.credit) for l in comb_lines)
                    if currency.is_zero(amount):
                        best = [l.id for l in comb_lines]
                        break
                if best:
                    break
            if best:
                default.extend(best)
        return default

    def transition_reconcile(self):
        pool = Pool()
        Line = pool.get('account.move.line')

        if self.show.lines:
            Line.reconcile(self.show.lines,
                journal=self.show.journal,
                date=self.show.date,
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
        'required': Bool(Eval('write_off', 0)),
        'invisible': ~Eval('write_off', 0),
        }
    _write_off_depends = ['write_off']

    write_off = fields.Function(fields.Numeric('Write-Off',
            digits=(16, Eval('currency_digits', 2)),
            states=_write_off_states,
            depends=_write_off_depends + ['currency_digits']),
        'on_change_with_write_off')
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    journal = fields.Many2One('account.journal', 'Journal',
        states=_write_off_states, depends=_write_off_depends,
        domain=[
            ('type', '=', 'write-off'),
            ])
    date = fields.Date('Date',
        states=_write_off_states, depends=_write_off_depends)
    description = fields.Char('Description',
        states=_write_off_states, depends=_write_off_depends)

    @fields.depends('lines')
    def on_change_with_write_off(self, name=None):
        return sum((l.debit - l.credit) for l in self.lines)

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
            for lines in to_reconcile.itervalues():
                Line.reconcile(lines)
        return 'end'


class CancelMovesDefault(ModelView):
    'Cancel Moves'
    __name__ = 'account.move.cancel.default'
    description = fields.Char('Description')


class FiscalYearLine(ModelSQL):
    'Fiscal Year - Move Line'
    __name__ = 'account.fiscalyear-account.move.line'
    _table = 'account_fiscalyear_line_rel'
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
            ondelete='CASCADE', select=True)
    line = fields.Many2One('account.move.line', 'Line', ondelete='RESTRICT',
            select=True, required=True)


class FiscalYear2:
    __metaclass__ = PoolMeta
    __name__ = 'account.fiscalyear'
    close_lines = fields.Many2Many('account.fiscalyear-account.move.line',
            'fiscalyear', 'line', 'Close Lines')


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
