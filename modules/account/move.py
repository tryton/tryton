# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from decimal import Decimal
from itertools import chain, groupby, islice

from dateutil.relativedelta import relativedelta
from sql import Literal, Null, Window
from sql.aggregate import Sum
from sql.conditionals import Case, Coalesce
from sql.functions import Abs, CharLength, Round
from sql.operators import Exists

from trytond import backend
from trytond.i18n import gettext
from trytond.model import (
    Check, DeactivableMixin, Index, ModelSQL, ModelView, dualmethod, fields)
from trytond.model.exceptions import AccessError
from trytond.modules.currency.fields import Monetary
from trytond.pool import Pool
from trytond.pyson import Bool, Eval, If, PYSONEncoder
from trytond.report import Report
from trytond.rpc import RPC
from trytond.tools import (
    firstline, grouped_slice, reduce_ids, sqlite_apply_types)
from trytond.transaction import Transaction, check_access
from trytond.wizard import (
    Button, StateAction, StateTransition, StateView, Wizard)

from .exceptions import (
    AccountMissing, CancelDelegatedWarning, CancelWarning, CopyWarning,
    DelegateLineError, GroupLineError, JournalMissing, PeriodNotFoundError,
    PostError, ReconciliationDeleteWarning, ReconciliationError,
    RescheduleLineError)

_MOVE_STATES = {
    'readonly': Eval('state') == 'posted',
    }
_LINE_STATES = {
    'readonly': Eval('state') == 'valid',
    }


class DescriptionOriginMixin:
    __slots__ = ()

    description_used = fields.Function(
        fields.Char("Description", states=_MOVE_STATES),
        'on_change_with_description_used',
        setter='set_description_used',
        searcher='search_description_used')

    @fields.depends('description', 'origin')
    def on_change_with_description_used(self, name=None):
        description = self.description
        if not description and hasattr(self.origin, 'description'):
            description = firstline(self.origin.description or '')
        return description

    @classmethod
    def set_description_used(cls, moves, name, value):
        moves = [m for m in moves if m.description_used != value]
        if moves:
            cls.write(moves, {'description': value})

    @classmethod
    def search_description_used(cls, name, clause):
        pool = Pool()
        domain = ['OR', [
                ('description', '!=', None),
                ('description', '!=', ''),
                ('description', *clause[1:]),
                ],
            ]
        for origin, _ in cls.get_origin():
            if not origin:
                continue
            Model = pool.get(origin)
            if 'description' in Model._fields:
                domain.append(
                    ('origin.description', *clause[1:3], origin, *clause[3:]))
        return domain


class Move(DescriptionOriginMixin, ModelSQL, ModelView):
    'Account Move'
    __name__ = 'account.move'
    _rec_name = 'number'
    number = fields.Char('Number', required=True, readonly=True)
    post_number = fields.Char('Post Number', readonly=True,
        help='Also known as Folio Number.')
    company = fields.Many2One('company.company', 'Company', required=True,
        states=_MOVE_STATES)
    period = fields.Many2One('account.period', 'Period', required=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            If(Eval('state') == 'draft',
                ('state', '=', 'open'),
                ()),
            If(Eval('date', None), [
                    ('start_date', '<=', Eval('date', None)),
                    ('end_date', '>=', Eval('date', None)),
                    ],
                []),
            ],
        states=_MOVE_STATES)
    journal = fields.Many2One('account.journal', 'Journal', required=True,
        states={
            'readonly': Eval('number') & Eval('journal', None),
            },
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    date = fields.Date('Effective Date', required=True, states=_MOVE_STATES)
    post_date = fields.Date('Post Date', readonly=True)
    description = fields.Char('Description', states=_MOVE_STATES)
    origin = fields.Reference('Origin', selection='get_origin',
        states=_MOVE_STATES)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ], 'State', required=True, readonly=True, sort=False)
    lines = fields.One2Many('account.move.line', 'move', 'Lines',
        states=_MOVE_STATES, depends={'company'},
        context={
            'journal': Eval('journal', -1),
            'period': Eval('period', -1),
            'date': Eval('date', None),
            })

    @classmethod
    def __setup__(cls):
        cls.number.search_unaccented = False
        cls.post_number.search_unaccented = False
        super(Move, cls).__setup__()
        t = cls.__table__()
        cls.create_date.select = True
        cls._check_modify_exclude = ['lines']
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
        cls._sql_indexes.update({
                Index(t, (t.period, Index.Range())),
                Index(t, (t.date, Index.Range()), (t.number, Index.Range())),
                Index(
                    t,
                    (t.journal, Index.Range()),
                    (t.period, Index.Range())),
                })

    @classmethod
    def order_number(cls, tables):
        table, _ = tables[None]
        return [CharLength(table.number), table.number]

    @classmethod
    def order_post_number(cls, tables):
        table, _ = tables[None]
        return [CharLength(table.post_number), table.post_number]

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @classmethod
    def default_period(cls):
        Period = Pool().get('account.period')
        company = cls.default_company()
        try:
            period = Period.find(company)
        except PeriodNotFoundError:
            return None
        return period.id

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
            start_date = period.start_date
            end_date = period.end_date
            if start_date <= today <= end_date:
                return today
            elif start_date >= today:
                return start_date
            else:
                return end_date

    @fields.depends('date', 'period', 'company', 'lines')
    def on_change_date(self):
        pool = Pool()
        Period = pool.get('account.period')
        context = Transaction().context
        if self.date:
            company = self.company or context.get('company')
            if (not self.period
                    or not (
                        self.period.start_date <= self.date
                        <= self.period.end_date)):
                try:
                    self.period = Period.find(company, date=self.date)
                except PeriodNotFoundError:
                    self.period = None
        for line in (self.lines or []):
            line.date = self.date

    @fields.depends(
        'period', 'date', 'company', 'journal', methods=['on_change_date'])
    def on_change_period(self):
        pool = Pool()
        Date = pool.get('ir.date')
        Line = pool.get('account.move.line')
        context = Transaction().context
        company_id = (
            self.company.id if self.company else context.get('company'))
        with Transaction().set_context(company=company_id):
            today = Date.today()
        if self.period:
            start_date = self.period.start_date
            end_date = self.period.end_date
            if (not self.date
                    or not (start_date <= self.date <= end_date)):
                if start_date <= today <= end_date:
                    self.date = today
                else:
                    lines = Line.search([
                            ('company', '=', company_id),
                            ('journal', '=', self.journal),
                            ('period', '=', self.period),
                            ],
                        order=[('date', 'DESC')], limit=1)
                    if lines:
                        line, = lines
                        self.date = line.date
                    elif start_date >= today:
                        self.date = start_date
                    else:
                        self.date = end_date
            self.on_change_date()

    @classmethod
    def _get_origin(cls):
        'Return list of Model names for origin Reference'
        return ['account.fiscalyear', 'account.move']

    @classmethod
    def get_origin(cls):
        Model = Pool().get('ir.model')
        get_name = Model.get_name
        models = cls._get_origin()
        return [(None, '')] + [(m, get_name(m)) for m in models]

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
        args = []
        for moves, values in zip(actions, actions):
            keys = list(values.keys())
            for key in cls._check_modify_exclude:
                if key in keys:
                    keys.remove(key)
            if len(keys):
                cls.check_modify(moves)
            args.extend((moves, values))
        super(Move, cls).write(*args)

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Journal = pool.get('account.journal')
        context = Transaction().context

        default_company = cls.default_company()
        vlist = [x.copy() for x in vlist]
        missing_number = defaultdict(list)
        for vals in vlist:
            if not vals.get('number'):
                journal_id = vals.get('journal', context.get('journal'))
                company_id = vals.get('company', default_company)
                if journal_id:
                    missing_number[(journal_id, company_id)].append(vals)
        for (journal_id, company_id), values in missing_number.items():
            journal = Journal(journal_id)
            sequence = journal.get_multivalue('sequence', company=company_id)
            with Transaction().set_context(company=company_id):
                for vals, number in zip(
                        values, sequence.get_many(len(values))):
                    vals['number'] = number
        return super().create(vlist)

    @classmethod
    def delete(cls, moves):
        MoveLine = Pool().get('account.move.line')
        cls.check_modify(moves)
        MoveLine.delete([l for m in moves for l in m.lines])
        super(Move, cls).delete(moves)

    @classmethod
    def copy(cls, moves, default=None):
        pool = Pool()
        Date = pool.get('ir.date')
        Period = pool.get('account.period')
        Warning = pool.get('res.user.warning')

        if default is None:
            default = {}
        else:
            default = default.copy()

        def _check_period(origin):
            period = Period(origin['period'])
            if period.state == 'closed':
                move = cls(origin['id'])
                key = Warning.format('copy', [move])
                if Warning.check(key):
                    raise CopyWarning(key,
                        gettext('account.msg_move_copy_closed_period',
                            move=move))
                return False
            else:
                return True

        def default_period(origin):
            if not _check_period(origin):
                with Transaction().set_context(company=origin['company']):
                    today = Date.today()
                period = Period.find(origin['company'], date=today)
                return period.id
            else:
                return origin['period']

        def default_date(origin):
            if not _check_period(origin):
                with Transaction().set_context(company=origin['company']):
                    return Date.today()
            else:
                return origin['date']

        default.setdefault('number', None)
        default.setdefault('post_number', None)
        default.setdefault('state', cls.default_state())
        default.setdefault('post_date', None)
        default.setdefault('period', default_period)
        default.setdefault('date', default_date)
        return super().copy(moves, default=default)

    @classmethod
    def validate_move(cls, moves):
        '''
        Validate balanced move
        '''
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        line = MoveLine.__table__()
        transaction = Transaction()
        cursor = transaction.connection.cursor()

        for company, moves in groupby(moves, key=lambda m: m.company):
            currency = company.currency
            for sub_moves in grouped_slice(list(moves)):
                red_sql = reduce_ids(line.move, [m.id for m in sub_moves])

                valid_move_query = line.select(
                    line.move,
                    where=red_sql,
                    group_by=line.move,
                    having=Abs(Round(
                            Sum(line.debit - line.credit),
                            currency.digits)) < abs(currency.rounding))
                cursor.execute(*line.update(
                        [line.state],
                        ['valid'],
                        where=line.move.in_(valid_move_query)))

                draft_move_query = line.select(
                    line.move,
                    where=red_sql,
                    group_by=line.move,
                    having=Abs(Round(
                            Sum(line.debit - line.credit),
                            currency.digits)) >= abs(currency.rounding))
                cursor.execute(*line.update(
                        [line.state],
                        ['draft'],
                        where=line.move.in_(draft_move_query)))

        Transaction().counter += 1
        for cache in Transaction().cache.values():
            if MoveLine.__name__ in cache:
                cache_cls = cache[MoveLine.__name__]
                cache_cls.clear()

    def _cancel_default(self, reversal=False):
        'Return default dictionary to cancel move'
        pool = Pool()
        Date = pool.get('ir.date')
        Period = pool.get('account.period')
        Warning = pool.get('res.user.warning')

        default = {
            'origin': str(self),
            }
        if self.period.state == 'closed':
            key = '%s.cancel' % self
            if Warning.check(key):
                raise CancelWarning(key,
                    gettext('account.msg_move_cancel_closed_period',
                        move=self.rec_name))
            with Transaction().set_context(company=self.company.id):
                date = Date.today()
            period = Period.find(self.company, date=date)
            default.update({
                    'date': date,
                    'period': period.id,
                    })
        if reversal:
            default['lines.debit'] = lambda data: data['credit']
            default['lines.credit'] = lambda data: data['debit']
        else:
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

    def cancel(self, default=None, reversal=False):
        'Return a cancel move'
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.update(self._cancel_default(reversal=reversal))
        cancel_move, = self.copy([self], default=default)
        return cancel_move

    @dualmethod
    @ModelView.button
    def post(cls, moves):
        pool = Pool()
        Date = pool.get('ir.date')
        Line = pool.get('account.move.line')
        move = cls.__table__()
        line = Line.__table__()
        cursor = Transaction().connection.cursor()

        to_reconcile = []

        for company, c_moves in groupby(moves, lambda m: m.company):
            with Transaction().set_context(company=company.id):
                today = Date.today()
            currency = company.currency
            c_moves = list(c_moves)
            for sub_moves in grouped_slice(c_moves):
                sub_moves_ids = [m.id for m in sub_moves]

                cursor.execute(*move.select(
                        move.id,
                        where=reduce_ids(move.id, sub_moves_ids)
                        & ~Exists(line.select(
                                line.move,
                                where=line.move == move.id))))
                try:
                    move_id, = cursor.fetchone()
                except TypeError:
                    pass
                else:
                    raise PostError(
                        gettext('account.msg_post_empty_move',
                            move=cls(move_id).rec_name))

                cursor.execute(*line.select(
                        line.move,
                        where=reduce_ids(line.move, sub_moves_ids),
                        group_by=line.move,
                        having=Abs(Round(
                                Sum(line.debit - line.credit),
                                currency.digits)) >= abs(currency.rounding)))
                try:
                    move_id, = cursor.fetchone()
                except TypeError:
                    pass
                else:
                    raise PostError(
                        gettext('account.msg_post_unbalanced_move',
                            move=cls(move_id).rec_name))

                cursor.execute(*line.select(
                        line.id,
                        where=reduce_ids(line.move, sub_moves_ids)
                        & (line.debit == Decimal(0))
                        & (line.credit == Decimal(0))
                        & ((line.amount_second_currency == Null)
                            | (line.amount_second_currency == Decimal(0)))
                        ))
                to_reconcile.extend(l for l, in cursor)

            missing_number = defaultdict(list)
            for move in c_moves:
                move.state = 'posted'
                if not move.post_number:
                    move.post_date = today
                    missing_number[move.period.post_move_sequence_used].append(
                        move)

            for sequence, m_moves in missing_number.items():
                for move, number in zip(
                        m_moves, sequence.get_many(len(m_moves))):
                    move.post_number = number

        cls.save(moves)

        def keyfunc(line):
            # Set party last to avoid compare party instance and None
            # party will always be None for the same account
            return line.account, line.party
        to_reconcile = Line.browse(sorted(
                [l for l in Line.browse(to_reconcile) if l.account.reconcile],
                key=keyfunc))
        to_reconcile = [list(l) for _, l in groupby(to_reconcile, keyfunc)]
        if to_reconcile:
            Line.reconcile(*to_reconcile)


class Reconciliation(ModelSQL, ModelView):
    'Account Move Reconciliation Lines'
    __name__ = 'account.move.reconciliation'
    _rec_name = 'number'
    number = fields.Char("Number", required=True)
    company = fields.Many2One('company.company', "Company", required=True)
    lines = fields.One2Many(
        'account.move.line', 'reconciliation', 'Lines',
        domain=[
            ('move.company', '=', Eval('company', -1)),
            ])
    date = fields.Date(
        "Date", required=True,
        help='Highest date of the reconciled lines.')
    delegate_to = fields.Many2One(
        'account.move.line', "Delegate To", ondelete="RESTRICT",
        domain=[
            ('move.company', '=', Eval('company', -1)),
            ],
        help="The line to which the reconciliation status is delegated.")

    @classmethod
    def __setup__(cls):
        cls.number.search_unaccented = False
        super().__setup__()
        t = cls.__table__()
        cls._sql_indexes.add(Index(t, (t.date, Index.Range())))

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        table = cls.__table_handler__(module_name)
        sql_table = cls.__table__()
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        move = Move.__table__()
        line = Line.__table__()
        line_h = Line.__table_handler__(module_name)

        company_exist = table.column_exist('company')

        # Migration from 6.6: rename name to number
        if table.column_exist('name') and not table.column_exist('number'):
            table.column_rename('name', 'number')

        super(Reconciliation, cls).__register__(module_name)

        # Migration from 5.8: add company field
        if not company_exist and line_h.column_exist('reconciliation'):
            value = (line
                .join(move, condition=line.move == move.id)
                .select(
                    move.company,
                    where=line.reconciliation == sql_table.id,
                    group_by=move.company))
            cursor.execute(*sql_table.update([sql_table.company], [value]))

    @classmethod
    def order_number(cls, tables):
        table, _ = tables[None]
        return [CharLength(table.number), table.number]

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        configuration = Configuration(1)

        vlist = [x.copy() for x in vlist]
        default_company = cls.default_company()
        for vals in vlist:
            if 'number' not in vals:
                vals['number'] = configuration.get_multivalue(
                    'reconciliation_sequence',
                    company=vals.get('company', default_company)).get()

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
                key = Warning.format('delete.delegated', [reconciliation])
                if Warning.check(key):
                    raise ReconciliationDeleteWarning(key,
                        gettext('account.msg_reconciliation_delete_delegated',
                            reconciliation=reconciliation.rec_name,
                            line=reconciliation.delegate_to.rec_name,
                            move=reconciliation.delegate_to.move.rec_name))
            for line in reconciliation.lines:
                if line.move.journal.type == 'write-off':
                    key = Warning.format('delete.write-off', [reconciliation])
                    if Warning.check(key):
                        raise ReconciliationDeleteWarning(key,
                            gettext(
                                'account.msg_reconciliation_delete_write_off',
                                reconciliation=reconciliation.rec_name,
                                line=line.rec_name,
                                move=line.move.rec_name))
        super().delete(reconciliations)

    @classmethod
    def check_lines(cls, reconciliations):
        Lang = Pool().get('ir.lang')
        for reconciliation in reconciliations:
            debit = Decimal(0)
            credit = Decimal(0)
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
            if not reconciliation.company.currency.is_zero(debit - credit):
                lang = Lang.get()
                debit = lang.currency(debit, reconciliation.company.currency)
                credit = lang.currency(credit, reconciliation.company.currency)
                raise ReconciliationError(
                    gettext('account.msg_reconciliation_unbalanced',
                        debit=debit,
                        credit=credit))


class MoveLineMixin:
    __slots__ = ()

    @classmethod
    def get_move_origin(cls):
        Move = Pool().get('account.move')
        return Move.get_origin()

    @classmethod
    def get_move_states(cls):
        pool = Pool()
        Move = pool.get('account.move')
        return Move.fields_get(['state'])['state']['selection']

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
        pool = Pool()
        Move = pool.get('account.move')
        if name.startswith('move_'):
            name = name[5:]
        if not value:
            return
        moves = {line.move for line in lines}
        moves = Move.browse(moves)
        Move.write(moves, {
                name: value,
                })

    @classmethod
    def search_move_field(cls, name, clause):
        nested = clause[0][len(name):]
        if name.startswith('move_'):
            name = name[5:]
        return [('move.' + name + nested, *clause[1:])]

    @staticmethod
    def _order_move_field(name):
        def order_field(cls, tables):
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
        return classmethod(order_field)

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
        return currency.id

    @classmethod
    def get_payable_receivable_balance(cls, lines, name):
        pool = Pool()
        Account = pool.get('account.account')
        AccountType = pool.get('account.account.type')
        Move = pool.get('account.move')

        transaction = Transaction()
        database = transaction.database
        context = transaction.context
        cursor = transaction.connection.cursor()

        line = cls.__table__()
        account = Account.__table__()
        account_type = AccountType.__table__()
        move = Move.__table__()

        balances = dict.fromkeys(map(int, lines))

        for company, lines in groupby(lines, lambda l: l.company):
            for sub_lines in grouped_slice(lines):
                sub_lines = list(sub_lines)
                id2currency = {
                    l.id: l.second_currency or company.currency
                    for l in sub_lines}
                where = account.company == company.id
                where_type = Literal(False)
                if context.get('receivable', True):
                    where_type |= account_type.receivable
                if context.get('payable', True):
                    where_type |= account_type.payable
                where &= where_type
                if not context.get('reconciled'):
                    if hasattr(cls, 'reconciliation'):
                        where &= line.reconciliation == Null
                    elif hasattr(cls, 'reconciled'):
                        where &= ~line.reconciled

                currency = Coalesce(line.second_currency, company.currency.id)
                sign = Case(
                    (account_type.statement == 'income', -1),
                    else_=1)
                balance = sign * Case(
                    (line.amount_second_currency != Null,
                        line.amount_second_currency),
                    else_=line.debit - line.credit)
                if database.has_window_functions():
                    balance = Sum(balance,
                        window=Window(
                            [line.party, currency],
                            order_by=[
                                Coalesce(line.maturity_date, move.date).asc,
                                move.date.desc,
                                line.id.desc,
                                ]))

                party_where = Literal(False)
                parties = {l.party for l in sub_lines}
                if None in parties:
                    party_where |= line.party == parties.discard(None)
                party_where |= reduce_ids(line.party, map(int, parties))
                where &= party_where

                query = (line
                    .join(move, condition=line.move == move.id)
                    .join(account, condition=line.account == account.id)
                    .join(
                        account_type,
                        condition=account.type == account_type.id)
                    .select(
                        line.id.as_('id'), balance.as_('balance'),
                        where=where))
                query = query.select(
                    query.id, query.balance.as_('balance'),
                    where=reduce_ids(query.id, [l.id for l in sub_lines]))
                if backend.name == 'sqlite':
                    sqlite_apply_types(query, [None, 'NUMERIC'])
                cursor.execute(*query)
                balances.update(
                    (i, id2currency[i].round(a)) for (i, a) in cursor)
        return balances

    def get_rec_name(self, name):
        if self.debit > self.credit:
            return self.account.rec_name
        else:
            return '(%s)' % self.account.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('account.rec_name',) + tuple(clause[1:])]


class Line(DescriptionOriginMixin, MoveLineMixin, ModelSQL, ModelView):
    'Account Move Line'
    __name__ = 'account.move.line'

    _states = {
        'readonly': Eval('move_state') == 'posted',
        }

    debit = Monetary(
        "Debit", currency='currency', digits='currency', required=True,
        states=_states,
        depends={'credit', 'tax_lines', 'journal'})
    credit = Monetary(
        "Credit", currency='currency', digits='currency', required=True,
        states=_states,
        depends={'debit', 'tax_lines', 'journal'})
    account = fields.Many2One('account.account', 'Account', required=True,
        domain=[
            ('company', '=', Eval('company', -1)),
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
        context={
            'company': Eval('company', -1),
            'period': Eval('period', -1),
            },
        states=_states, depends={'company', 'period'})
    move = fields.Many2One(
        'account.move', "Move", required=True,
        ondelete='CASCADE',
        states={
            'required': False,
            'readonly': (((Eval('state') == 'valid') | _states['readonly'])
                & Bool(Eval('move'))),
            })
    journal = fields.Function(fields.Many2One(
            'account.journal', 'Journal',
            states=_states,
            context={
                'company': Eval('company', -1),
                },
            depends={'company'}),
        'get_move_field', setter='set_move_field',
        searcher='search_move_field')
    period = fields.Function(fields.Many2One('account.period', 'Period',
            states=_states),
            'get_move_field', setter='set_move_field',
            searcher='search_move_field')
    company = fields.Function(fields.Many2One(
            'company.company', "Company", states=_states),
        'get_move_field', setter='set_move_field',
        searcher='search_move_field')
    date = fields.Function(fields.Date('Effective Date', required=True,
            states=_states),
            'on_change_with_date', setter='set_move_field',
            searcher='search_move_field')
    origin = fields.Reference(
        "Origin", selection='get_origin', states=_states)
    move_origin = fields.Function(
        fields.Reference("Move Origin", selection='get_move_origin'),
        'get_move_field', searcher='search_move_field')
    description = fields.Char('Description', states=_states)
    move_description_used = fields.Function(
        fields.Char("Move Description", states=_states),
        'get_move_field',
        setter='set_move_field',
        searcher='search_move_field')
    amount_second_currency = Monetary(
        "Amount Second Currency",
        currency='second_currency', digits='second_currency',
        states={
            'required': Bool(Eval('second_currency')),
            'readonly': _states['readonly'],
            },
        help='The amount expressed in a second currency.')
    second_currency = fields.Many2One('currency.currency', 'Second Currency',
            help='The second currency.',
        domain=[
            If(~Eval('second_currency_required'),
                ('id', '!=', Eval('currency', -1)),
                ('id', '=', Eval('second_currency_required', -1))),
            ],
        states={
            'required': (Bool(Eval('amount_second_currency'))
                | Bool(Eval('second_currency_required'))),
            'readonly': _states['readonly']
            })
    second_currency_required = fields.Function(
        fields.Many2One('currency.currency', "Second Currency Required"),
        'on_change_with_second_currency_required')
    party = fields.Many2One(
        'party.party', "Party",
        states={
            'required': Eval('party_required', False),
            'invisible': ~Eval('party_required', False),
            'readonly': _states['readonly'],
            },
        context={
            'company': Eval('company', -1),
            },
        depends={'company'}, ondelete='RESTRICT')
    party_required = fields.Function(fields.Boolean('Party Required'),
        'on_change_with_party_required')
    maturity_date = fields.Date(
        "Maturity Date",
        states={
            'invisible': ~Eval('has_maturity_date'),
            },
        depends=['has_maturity_date'],
        help="Set a date to make the line payable or receivable.")
    has_maturity_date = fields.Function(
        fields.Boolean("Has Maturity Date"),
        'on_change_with_has_maturity_date')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('valid', 'Valid'),
        ], 'State', readonly=True, required=True, sort=False)
    reconciliation = fields.Many2One(
        'account.move.reconciliation', 'Reconciliation',
        readonly=True, ondelete='SET NULL')
    reconciliations_delegated = fields.One2Many(
        'account.move.reconciliation', 'delegate_to',
        "Reconciliations Delegated", readonly=True)
    tax_lines = fields.One2Many('account.tax.line', 'move_line', 'Tax Lines')
    move_state = fields.Function(
        fields.Selection('get_move_states', "Move State"),
        'on_change_with_move_state', searcher='search_move_field')
    currency = fields.Function(fields.Many2One(
            'currency.currency', "Currency"),
        'on_change_with_currency', searcher='search_currency')
    amount = fields.Function(Monetary(
            "Amount", currency='amount_currency', digits='amount_currency'),
        'get_amount')
    amount_currency = fields.Function(fields.Many2One('currency.currency',
            'Amount Currency'), 'get_amount_currency')
    delegated_amount = fields.Function(Monetary(
            "Delegated Amount",
            currency='amount_currency', digits='amount_currency',
            states={
                'invisible': (
                    ~Eval('reconciliation', False)
                    | ~Eval('delegated_amount', 0)),
                }),
        'get_delegated_amount')
    payable_receivable_balance = fields.Function(
        Monetary(
            "Payable/Receivable Balance",
            currency='amount_currency', digits='amount_currency'),
        'get_payable_receivable_balance')

    del _states

    @classmethod
    def __setup__(cls):
        super(Line, cls).__setup__()
        cls.__access__.add('move')
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
        # Do not cache default_date nor default_move
        cls.__rpc__['default_get'].cache = None
        cls._order[0] = ('id', 'DESC')
        cls._sql_indexes.update({
                Index(
                    table,
                    (table.account, Index.Range()),
                    (table.party, Index.Range())),
                Index(table, (table.reconciliation, Index.Range())),
                # Index for General Ledger
                Index(
                    table,
                    (table.move, Index.Range()),
                    (table.account, Index.Range())),
                # Index for account.account.party
                Index(
                    table,
                    (table.account, Index.Range()),
                    (table.party, Index.Range()),
                    (table.id, Index.Range(cardinality='high')),
                    where=table.party != Null),
                # Index for receivable/payable balance
                Index(
                    table,
                    (table.account, Index.Range()),
                    (table.party, Index.Range()),
                    where=table.reconciliation == Null),
                })

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
        context = Transaction().context

        date = Date.today()
        lines = cls.search([
                ('company', '=', context.get('company')),
                ('journal', '=', context.get('journal')),
                ('period', '=', context.get('period')),
                ],
            order=[('date', 'DESC')], limit=1)
        if lines:
            line, = lines
            date = line.date
        elif context.get('period'):
            period = Period(context['period'])
            if period.start_date >= date:
                date = period.start_date
            else:
                date = period.end_date
        if context.get('date'):
            date = context['date']
        return date

    @classmethod
    def default_move(cls):
        transaction = Transaction()
        context = transaction.context
        if context.get('journal') and context.get('period'):
            lines = cls.search([
                    ('company', '=', context.get('company')),
                    ('move.journal', '=', context['journal']),
                    ('move.period', '=', context['period']),
                    ('create_uid', '=', transaction.user),
                    ('state', '=', 'draft'),
                    ], order=[('id', 'DESC')], limit=1)
            if lines:
                line, = lines
                return line.move.id

    @fields.depends(
        'move', 'debit', 'credit',
        '_parent_move.lines', '_parent_move.company')
    def on_change_move(self):
        if self.move:
            if not self.debit and not self.credit:
                total = sum((l.debit or 0) - (l.credit or 0)
                    for l in getattr(self.move, 'lines', []))
                self.debit = -total if total < 0 else Decimal(0)
                self.credit = total if total > 0 else Decimal(0)
            self.company = self.move.company

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_debit():
        return Decimal(0)

    @staticmethod
    def default_credit():
        return Decimal(0)

    @fields.depends('account')
    def on_change_with_currency(self, name=None):
        return self.account.currency if self.account else None

    @classmethod
    def search_currency(cls, name, clause):
        return [('account.company.' + clause[0], * clause[1:])]

    @classmethod
    def _get_origin(cls):
        'Return list of Model names for origin Reference'
        return ['account.move.line']

    @classmethod
    def get_origin(cls):
        Model = Pool().get('ir.model')
        get_name = Model.get_name
        models = cls._get_origin()
        return [(None, '')] + [(m, get_name(m)) for m in models]

    @property
    def origin_rec_name(self):
        if self.origin:
            return self.origin.rec_name
        elif self.move_origin:
            return self.move_origin.rec_name
        else:
            return ''

    @fields.depends('debit', 'credit', 'amount_second_currency')
    def on_change_debit(self):
        if self.debit:
            self.credit = Decimal(0)
        self._amount_second_currency_sign()

    @fields.depends('debit', 'credit', 'amount_second_currency')
    def on_change_credit(self):
        if self.credit:
            self.debit = Decimal(0)
        self._amount_second_currency_sign()

    @fields.depends('amount_second_currency', 'debit', 'credit')
    def on_change_amount_second_currency(self):
        self._amount_second_currency_sign()

    def _amount_second_currency_sign(self):
        'Set correct sign to amount_second_currency'
        if self.amount_second_currency:
            self.amount_second_currency = \
                self.amount_second_currency.copy_sign(
                    (self.debit or 0) - (self.credit or 0))

    @fields.depends('account')
    def on_change_account(self):
        if self.account:
            if self.account.second_currency:
                self.second_currency = self.account.second_currency
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

    @fields.depends('move', '_parent_move.date')
    def on_change_with_date(self, name=None):
        if self.move:
            return self.move.date

    @fields.depends('move', '_parent_move.state')
    def on_change_with_move_state(self, name=None):
        if self.move:
            return self.move.state

    @classmethod
    def order_maturity_date(self, tables):
        pool = Pool()
        Move = pool.get('account.move')
        table, _ = tables[None]
        if 'move' not in tables:
            move = Move.__table__()
            tables['move'] = {
                None: (move, table.move == move.id),
                }
        else:
            move, _ = tables['move'][None]
        return [Coalesce(table.maturity_date, move.date)]

    @fields.depends('account')
    def on_change_with_has_maturity_date(self, name=None):
        if self.account:
            type_ = self.account.type
            return type_.receivable or type_.payable

    order_journal = MoveLineMixin._order_move_field('journal')
    order_period = MoveLineMixin._order_move_field('period')
    order_company = MoveLineMixin._order_move_field('company')
    order_date = MoveLineMixin._order_move_field('date')
    order_move_origin = MoveLineMixin._order_move_field('origin')
    order_move_state = MoveLineMixin._order_move_field('state')

    def get_delegated_amount(self, name):
        def final_delegated_line(line):
            if not line.reconciliation or not line.reconciliation.delegate_to:
                return line
            return final_delegated_line(line.reconciliation.delegate_to)

        final_delegation = final_delegated_line(self)
        if final_delegation == self:
            return None
        elif final_delegation.reconciliation:
            return final_delegation.amount_currency.round(0)
        else:
            return final_delegation.amount

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

        if context.get('journal'):
            where &= move.journal == context['journal']

        date = context.get('date')
        from_date, to_date = context.get('from_date'), context.get('to_date')
        fiscalyear_id = context.get('fiscalyear')
        period_ids = context.get('periods')
        if date:
            fiscalyears = FiscalYear.search([
                    ('start_date', '<=', date),
                    ('end_date', '>=', date),
                    ('company', '=', company),
                    ],
                order=[('start_date', 'DESC')],
                limit=1)
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
    def validate_fields(cls, lines, field_names):
        super(Line, cls).validate(lines)
        cls.check_account(lines, field_names)

    @classmethod
    def check_account(cls, lines, field_names=None):
        if field_names and not (field_names & {'account', 'party'}):
            return
        for line in lines:
            if not line.account.type or line.account.closed:
                raise AccessError(
                    gettext('account.msg_line_closed_account',
                        account=line.account.rec_name))
            if bool(line.party) != bool(line.account.party_required):
                error = 'party_set' if line.party else 'party_required'
                raise AccessError(
                    gettext('account.msg_line_%s' % error,
                        account=line.account.rec_name,
                        line=line.rec_name))

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
            if journal_period.state == 'closed':
                raise AccessError(
                    gettext('account.msg_modify_line_closed_journal_period',
                        journal_period=journal_period.rec_name))
        else:
            JournalPeriod.lock()
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
    def view_attributes(cls):
        attributes = super().view_attributes()
        view_ids = cls._view_reconciliation_muted()
        if Transaction().context.get('view_id') in view_ids:
            attributes.append(
                ('/tree', 'visual',
                    If(Bool(Eval('reconciliation')), 'muted', '')))
        return attributes

    @classmethod
    def _view_reconciliation_muted(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        return {ModelData.get_id(
                'account', 'move_line_view_list_payable_receivable')}

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

        def move_fields(move_name):
            for fname, field in cls._fields.items():
                if (isinstance(field, fields.Function)
                        and field.setter == 'set_move_field'):
                    if move_name and fname.startswith('move_'):
                        fname = fname[5:]
                    yield fname

        moves = {}
        context = Transaction().context
        vlist = [x.copy() for x in vlist]
        for vals in vlist:
            if not vals.get('move'):
                move_values = {}
                for fname in move_fields(move_name=True):
                    move_values[fname] = vals.get(fname) or context.get(fname)
                key = tuple(sorted(move_values.items()))
                move = moves.get(key)
                if move is None:
                    move = Move(**move_values)
                    move.save()
                    moves[key] = move
                vals['move'] = move.id
            else:
                # prevent default value for field with set_move_field
                for fname in move_fields(move_name=False):
                    vals.setdefault(fname, None)
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
        Move = pool.get('account.move')
        Lang = pool.get('ir.lang')
        lang = Lang.get()
        delegate_to = delegate_to.id if delegate_to else None

        reconciliations = []
        to_post = []
        for lines in lines_list:
            if not lines:
                continue
            for line in lines:
                if line.reconciliation:
                    raise AccessError(
                        gettext('account.msg_line_already_reconciled',
                            line=line.rec_name))

            lines = list(lines)
            reconcile_account = None
            reconcile_party = None
            amount = Decimal(0)
            amount_second_currency = Decimal(0)
            second_currencies = set()
            posted = True
            for line in lines:
                posted &= line.move.state == 'posted'
                amount += line.debit - line.credit
                if not reconcile_account:
                    reconcile_account = line.account
                if not reconcile_party:
                    reconcile_party = line.party
                if line.amount_second_currency is not None:
                    amount_second_currency += line.amount_second_currency
                second_currencies.add(line.second_currency)
            company = reconcile_account.company

            try:
                second_currency, = second_currencies
            except ValueError:
                amount_second_currency = None
                second_currency = None
            if second_currency:
                writeoff_amount = amount_second_currency
                writeoff_currency = second_currency
            else:
                writeoff_amount = amount
                writeoff_currency = company.currency
            if writeoff_amount:
                if not writeoff:
                    raise ReconciliationError(gettext(
                            'account.msg_reconciliation_write_off_missing',
                            amount=lang.currency(
                                writeoff_amount, writeoff_currency)))
                move = cls._get_writeoff_move(
                    reconcile_account, reconcile_party,
                    writeoff_amount, writeoff_currency,
                    writeoff, date=date, description=description)
                move.save()
                if posted:
                    to_post.append(move)
                for line in move.lines:
                    if line.account == reconcile_account:
                        lines.append(line)
                        amount += line.debit - line.credit
            if second_currency and amount:
                move = cls._get_exchange_move(
                    reconcile_account, reconcile_party, amount, date)
                move.save()
                if posted:
                    to_post.append(move)
                for line in move.lines:
                    if line.account == reconcile_account:
                        lines.append(line)
                        amount += line.debit - line.credit
            assert not amount, f"{amount} must be zero"
            reconciliations.append({
                    'company': reconcile_account.company,
                    'lines': [('add', [x.id for x in lines])],
                    'date': max(l.date for l in lines),
                    'delegate_to': delegate_to,
                    })
        if to_post:
            Move.post(to_post)
        return Reconciliation.create(reconciliations)

    @classmethod
    def _get_writeoff_move(
            cls, reconcile_account, reconcile_party, amount, currency,
            writeoff, date=None, description=None):
        pool = Pool()
        Currency = pool.get('currency.currency')
        Date = pool.get('ir.date')
        Period = pool.get('account.period')
        Move = pool.get('account.move')
        company = reconcile_account.company
        if not date:
            with Transaction().set_context(company=company.id):
                date = Date.today()
        period = Period.find(reconcile_account.company, date=date)
        if amount >= 0:
            account = writeoff.debit_account
        else:
            account = writeoff.credit_account
        if account == reconcile_account:
            raise ReconciliationError(gettext(
                    'account.msg_reconciliation_write_off_same_account',
                    write_off=writeoff.rec_name,
                    account=account.rec_name))

        journal = writeoff.journal

        if currency != company.currency:
            amount_second_currency = amount
            second_currency = currency
            with Transaction().set_context(date=date):
                amount = Currency.compute(
                    currency, amount, company.currency)
        else:
            amount_second_currency = None
            second_currency = None

        move = Move()
        move.company = company
        move.journal = journal
        move.period = period
        move.date = date
        move.description = description

        lines = []

        line = cls()
        lines.append(line)
        line.account = reconcile_account
        line.party = reconcile_party
        line.debit = -amount if amount < 0 else 0
        line.credit = amount if amount > 0 else 0
        if second_currency:
            line.amount_second_currency = (
                amount_second_currency).copy_sign(
                    line.debit - line.credit)
            line.second_currency = second_currency

        line = cls()
        lines.append(line)
        line.account = account
        line.party = (
            reconcile_party if account.party_required else None)
        line.debit = amount if amount > 0 else 0
        line.credit = -amount if amount < 0 else 0
        if account.second_currency:
            with Transaction().set_context(date=date):
                line.amount_second_currency = Currency.compute(
                    company.currency, amount,
                    reconcile_account.second_currency).copy_sign(
                        line.debit - line.credit)

        move.lines = lines
        return move

    @classmethod
    def _get_exchange_move(cls, account, party, amount, date=None):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        Date = pool.get('ir.date')
        Move = pool.get('account.move')
        Period = pool.get('account.period')

        configuration = Configuration(1)
        company = account.company
        if not date:
            with Transaction().set_context(company=company.id):
                date = Date.today()

        period_id = Period.find(company.id, date=date)

        move = Move()
        move.company = company
        move.journal = configuration.get_multivalue(
            'currency_exchange_journal', company=company.id)
        if not move.journal:
            raise JournalMissing(gettext(
                    'account.'
                    'msg_reconciliation_currency_exchange_journal_missing',
                    company=company.rec_name))
        move.period = period_id
        move.date = date

        lines = []

        line = cls()
        lines.append(line)
        line.account = account
        line.party = party
        line.debit = -amount if amount < 0 else 0
        line.credit = amount if amount > 0 else 0

        line = cls()
        lines.append(line)
        line.debit = amount if amount > 0 else 0
        line.credit = -amount if amount < 0 else 0
        if line.credit:
            line.account = configuration.get_multivalue(
                'currency_exchange_credit_account', company=company.id)
            if not line.account:
                raise AccountMissing(gettext(
                        'account.'
                        'msg_reconciliation_currency_exchange_'
                        'credit_account_missing',
                        company=company.rec_name))
        else:
            line.account = configuration.get_multivalue(
                'currency_exchange_debit_account', company=company.id)
            if not line.account:
                raise AccountMissing(gettext(
                        'account.'
                        'msg_reconciliation_currency_exchange_'
                        'debit_account_missing',
                        company=company.rec_name))

        move.lines = lines
        return move

    @classmethod
    def find_best_reconciliation(cls, lines, currency, amount=0):
        """Return the list of lines to reconcile for the amount
        with the smallest remaining.

        For performance reason it is an approximation that searches for the
        smallest remaining by removing the last line that decrease it."""
        assert len({l.account for l in lines}) <= 1

        def get_balance(line):
            if line.second_currency == currency:
                return line.amount_second_currency
            elif line.currency == currency:
                return line.debit - line.credit
            else:
                return 0

        lines = sorted(lines, key=cls._reconciliation_sort_key)
        debit, credit = [], []
        remaining = -amount
        for line in list(lines):
            balance = get_balance(line)
            if balance > 0:
                debit.append(line)
            elif balance < 0:
                credit.append(line)
            else:
                lines.remove(line)
            remaining += balance

        best_lines, best_remaining = list(lines), remaining
        if remaining:
            while lines:
                try:
                    line = (debit if remaining > 0 else credit).pop()
                except IndexError:
                    break
                lines.remove(line)
                remaining -= get_balance(line)
                if lines and abs(remaining) < abs(best_remaining):
                    best_lines, best_remaining = list(lines), remaining
                    if not remaining:
                        break
        return best_lines, best_remaining

    def _reconciliation_sort_key(self):
        return self.maturity_date or self.date


class LineReceivablePayableContext(ModelView):
    "Receivable/Payable Line Context"
    __name__ = 'account.move.line.receivable_payable.context'

    reconciled = fields.Boolean("Reconciled")
    receivable = fields.Boolean("Receivable")
    payable = fields.Boolean("Payable")

    @classmethod
    def default_reconciled(cls):
        return Transaction().context.get('reconciled', False)

    @classmethod
    def default_receivable(cls):
        return Transaction().context.get('receivable', True)

    @classmethod
    def default_payable(cls):
        return Transaction().context.get('payable', True)


class WriteOff(DeactivableMixin, ModelSQL, ModelView):
    'Reconcile Write Off'
    __name__ = 'account.move.reconcile.write_off'
    company = fields.Many2One('company.company', "Company", required=True)
    name = fields.Char("Name", required=True, translate=True)
    journal = fields.Many2One('account.journal', "Journal", required=True,
        domain=[('type', '=', 'write-off')],
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    credit_account = fields.Many2One('account.account', "Credit Account",
        required=True,
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('company', '=', Eval('company', -1)),
            ])
    debit_account = fields.Many2One('account.account', "Debit Account",
        required=True,
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('company', '=', Eval('company', -1)),
            ])

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
            ('state', '!=', 'closed'),
            ])

    @classmethod
    def default_period(cls):
        pool = Pool()
        Period = pool.get('account.period')
        company = Transaction().context.get('company')
        try:
            period = Period.find(company)
        except PeriodNotFoundError:
            return None
        return period.id


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
        if (self.model
                and self.model.__name__ == 'account.journal.period'
                and self.record):
            return 'open_'
        return 'ask'

    def default_ask(self, fields):
        if (self.model
                and self.model.__name__ == 'account.journal.period'
                and self.record):
            return {
                'journal': self.record.journal.id,
                'period': self.record.period.id,
                }
        return {}

    def do_open_(self, action):
        JournalPeriod = Pool().get('account.journal.period')

        if (self.model
                and self.model.__name__ == 'account.journal.period'
                and self.record):
            journal = self.record.journal
            period = self.record.period
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

        action['name'] += ' (%s)' % journal_period.rec_name
        action['pyson_domain'] = PYSONEncoder().encode([
            ('journal', '=', journal.id),
            ('period', '=', period.id),
            ('company', '=', period.company.id),
            ])
        action['pyson_context'] = PYSONEncoder().encode({
            'journal': journal.id,
            'period': period.id,
            'company': period.company.id,
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
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')
        context = Transaction().context

        company_id = self.record.company.id if self.record else -1
        date = context.get('date')
        fiscalyear = context.get('fiscalyear')
        if date:
            fiscalyears = FiscalYear.search([
                    ('start_date', '<=', date),
                    ('end_date', '>=', date),
                    ('company', '=', company_id),
                    ],
                order=[('start_date', 'DESC')],
                limit=1)
        elif fiscalyear:
            fiscalyears = [FiscalYear(fiscalyear)]
        else:
            fiscalyears = FiscalYear.search([
                    ('state', '=', 'open'),
                    ('company', '=', company_id),
                    ])
        periods = [p for f in fiscalyears for p in f.periods]

        action['pyson_domain'] = [
            ('period', 'in', [p.id for p in periods]),
            ('account', '=', self.record.id if self.record else None),
            ('state', '=', 'valid'),
            ]
        if Transaction().context.get('posted'):
            action['pyson_domain'].append(('move.state', '=', 'posted'))
        if Transaction().context.get('date'):
            action['pyson_domain'].append(('move.date', '<=',
                    Transaction().context['date']))
        if self.record:
            action['name'] += ' (%s)' % self.record.rec_name
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
            ('company', '=', Eval('company', -1)),
            ])
    date = fields.Date('Date', required=True)
    amount = Monetary(
        "Amount", currency='currency', digits='currency', readonly=True)
    currency = fields.Many2One('currency.currency', "Currency", readonly=True)
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

    @classmethod
    def check_access(cls, models=None):
        transaction = Transaction()
        if transaction.user:
            context = transaction.context
            models = set() if models is None else models.copy()
            models.update({'account.move.line', 'account.general_ledger.line'})
            model = context.get('active_model')
            if model and model not in models:
                raise AccessError(gettext(
                        'ir.msg_access_wizard_model_error',
                        wizard=cls.__name__,
                        model=model))
        super().check_access()

    def get_writeoff(self):
        "Return writeoff amount and company"
        company = currency = None
        amount = Decimal(0)
        amount_second_currency = Decimal(0)
        second_currencies = set()
        for line in self.records:
            amount += line.debit - line.credit
            if line.amount_second_currency is not None:
                amount_second_currency += line.amount_second_currency
            second_currencies.add(line.second_currency)
            if not company:
                company = line.account.company
                currency = company.currency
        try:
            second_currency, = second_currencies
        except ValueError:
            second_currency = None
        if second_currency:
            amount = amount_second_currency
            currency = second_currency
        return amount, currency, company

    def transition_start(self):
        amount, currency, company = self.get_writeoff()
        if not company:
            return 'end'
        if currency.is_zero(amount):
            return 'reconcile'
        return 'writeoff'

    def default_writeoff(self, fields):
        amount, currency, company = self.get_writeoff()
        return {
            'amount': amount,
            'currency': currency.id,
            'company': company.id,
            }

    def transition_reconcile(self):
        self.model.reconcile(
            self.records,
            writeoff=getattr(self.writeoff, 'writeoff', None),
            date=getattr(self.writeoff, 'date', None),
            description=getattr(self.writeoff, 'description', None))
        return 'end'


class UnreconcileLines(Wizard):
    'Unreconcile Lines'
    __name__ = 'account.move.unreconcile_lines'
    start_state = 'unreconcile'
    unreconcile = StateTransition()

    @classmethod
    def check_access(cls, models=None):
        transaction = Transaction()
        if transaction.user:
            context = transaction.context
            models = set() if models is None else models.copy()
            models.update({'account.move.line', 'account.general_ledger.line'})
            model = context.get('active_model')
            if model and model not in models:
                raise AccessError(gettext(
                        'ir.msg_access_wizard_model_error',
                        wizard=cls.__name__,
                        model=model))
        super().check_access()

    def transition_unreconcile(self):
        self.make_unreconciliation(self.records)
        return 'end'

    @classmethod
    def make_unreconciliation(cls, lines):
        pool = Pool()
        Reconciliation = pool.get('account.move.reconciliation')

        reconciliations = [x.reconciliation for x in lines if x.reconciliation]
        if reconciliations:
            Reconciliation.delete(reconciliations)


class Reconcile(Wizard):
    'Reconcile'
    __name__ = 'account.reconcile'
    start = StateView(
        'account.reconcile.start',
        'account.reconcile_start_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Reconcile", 'next_', 'tryton-ok', default=True),
            ])
    next_ = StateTransition()
    show = StateView('account.reconcile.show',
        'account.reconcile_show_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Skip', 'next_', 'tryton-forward', validate=False),
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

        if self.model and self.model.__name__ == 'account.move.line':
            lines = [l for l in self.records if not l.reconciliation]
            return list({l.account for l in lines if l.account.reconcile})

        balance = line.debit - line.credit
        cursor.execute(*line.join(account,
                condition=line.account == account.id)
            .join(account_type, condition=account.type == account_type.id)
            .select(
                account.id,
                where=((line.reconciliation == Null)
                    & (line.state == 'valid')
                    & account.reconcile
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
        return [a for a, in cursor]

    def get_parties(self, account, party=None):
        'Return a list party to reconcile for the account'
        pool = Pool()
        Line = pool.get('account.move.line')
        line = Line.__table__()
        cursor = Transaction().connection.cursor()

        if self.model and self.model.__name__ == 'account.move.line':
            lines = [l for l in self.records if not l.reconciliation]
            return list({l.party for l in lines if l.account == account})

        where = ((line.reconciliation == Null)
            & (line.state == 'valid')
            & (line.account == account.id))
        if party:
            where &= (line.party == party.id)
        cursor.execute(*line.select(line.party,
                where=where,
                group_by=line.party))
        return [p for p, in cursor]

    def get_currencies(self, account, party, currency=None, _balanced=False):
        "Return a list of currencies to reconcile for the account and party"
        pool = Pool()
        Line = pool.get('account.move.line')
        line = Line.__table__()
        cursor = Transaction().connection.cursor()

        if self.model and self.model.__name__ == 'account.move.line':
            lines = [l for l in self.records if not l.reconciliation]
            return list({
                    (l.second_currency or l.currency).id
                    for l in lines
                    if l.account == account and l.party == party})

        balance = Case(
            (line.second_currency != Null, line.amount_second_currency),
            else_=line.debit - line.credit)
        if _balanced:
            having = Sum(balance) == 0
        else:
            having = ((
                    Sum(Case((balance > 0, 1), else_=0)) > 0)
                & (Sum(Case((balance < 0, 1), else_=0)) > 0)
                | Case((account.type.receivable, Sum(balance) < 0),
                    else_=False)
                | Case((account.type.payable, Sum(balance) > 0),
                    else_=False)
                )
        where = ((line.reconciliation == Null)
            & (line.state == 'valid')
            & (line.account == account.id)
            & (line.party == (party.id if party else None)))
        currency_expr = Coalesce(line.second_currency, account.currency.id)
        if currency:
            where &= (currency_expr == currency.id)
        cursor.execute(*line.select(
                currency_expr,
                where=where,
                group_by=line.second_currency,
                having=having))
        return [p for p, in cursor]

    @check_access
    def transition_next_(self):
        pool = Pool()
        Line = pool.get('account.move.line')

        def next_account():
            accounts = list(self.show.accounts)
            if not accounts:
                return
            account = accounts.pop()
            self.show.account = account
            self.show.accounts = accounts
            self.show.parties = self.get_parties(account)
            return account

        def next_party():
            parties = list(self.show.parties)
            if not parties:
                return
            party = parties.pop()
            self.show.party = party
            self.show.parties = parties
            self.show.currencies = self.get_currencies(
                self.show.account, party)
            return party,

        def next_currency():
            currencies = list(self.show.currencies)
            if not currencies:
                return
            currency = currencies.pop()
            self.show.currency = currency
            self.show.currencies = currencies
            return currency

        if getattr(self.show, 'accounts', None) is None:
            self.show.accounts = self.get_accounts()
            if not (next_account() and next_party()):
                return 'end'
        if getattr(self.show, 'parties', None) is None:
            self.show.parties = self.get_parties(self.show.account)
            if not next_party():
                return 'end'
        if getattr(self.show, 'currencies', None) is None:
            self.show.currencies = self.get_currencies(
                self.show.account, self.show.party)

        while True:
            while not next_currency():
                while not next_party():
                    if not next_account():
                        return 'end'
            if self.start.automatic or self.start.only_balanced:
                lines = self._default_lines()
                if lines and self.start.automatic:
                    while lines:
                        Line.reconcile(lines)
                        lines = self._default_lines()
                    continue
                elif not lines and self.start.only_balanced:
                    continue
            return 'show'

    def default_show(self, fields):
        pool = Pool()
        Date = pool.get('ir.date')

        defaults = {}
        defaults['accounts'] = [a.id for a in self.show.accounts]
        defaults['account'] = self.show.account.id
        defaults['company'] = self.show.account.company.id
        defaults['parties'] = [p.id for p in self.show.parties]
        defaults['party'] = self.show.party.id if self.show.party else None
        defaults['currencies'] = [c.id for c in self.show.currencies]
        defaults['currency'] = (
            self.show.currency.id if self.show.currency else None)
        defaults['lines'] = list(map(int, self._default_lines()))
        defaults['write_off_amount'] = None
        with Transaction().set_context(company=self.show.account.company.id):
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
                ['OR',
                    [
                        ('currency', '=', self.show.currency.id),
                        ('second_currency', '=', None),
                        ],
                    ('second_currency', '=', self.show.currency.id),
                    ],
                ('state', '=', 'valid'),
                ],
            order=[])

    def _line_sort_key(self, line):
        return [line.maturity_date or line.date]

    def _default_lines(self):
        'Return the larger list of lines which can be reconciled'
        pool = Pool()
        Line = pool.get('account.move.line')

        if self.model and self.model.__name__ == 'account.move.line':
            requested = {
                l for l in self.records
                if l.account == self.show.account
                and l.party == self.show.party
                and (l.second_currency or l.currency) == self.show.currency}
        else:
            requested = []
        currency = self.show.currency

        lines, remaining = Line.find_best_reconciliation(
            self._all_lines(), currency)
        if remaining:
            return requested
        else:
            return lines

    def transition_reconcile(self):
        pool = Pool()
        Line = pool.get('account.move.line')

        if self.show.lines:
            Line.reconcile(self.show.lines,
                date=self.show.date,
                writeoff=self.show.write_off,
                description=self.show.description)

        if self.get_currencies(
                self.show.account, self.show.party,
                currency=self.show.currency):
            return 'show'
        return 'next_'


class ReconcileStart(ModelView):
    "Reconcile"
    __name__ = 'account.reconcile.start'
    automatic = fields.Boolean(
        "Automatic",
        help="Automatically reconcile suggestions.")
    only_balanced = fields.Boolean(
        "Only Balanced",
        help="Skip suggestion with write-off.")

    @classmethod
    def default_automatic(cls):
        return False

    @classmethod
    def default_only_balanced(cls):
        return False


class ReconcileShow(ModelView):
    'Reconcile'
    __name__ = 'account.reconcile.show'
    company = fields.Many2One('company.company', "Company", readonly=True)
    accounts = fields.Many2Many('account.account', None, None, 'Account',
        readonly=True)
    account = fields.Many2One('account.account', 'Account', readonly=True)
    parties = fields.Many2Many(
        'party.party', None, None, 'Parties', readonly=True,
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    party = fields.Many2One(
        'party.party', 'Party', readonly=True,
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    currencies = fields.Many2Many(
        'currency.currency', None, None, "Currencies", readonly=True)
    currency = fields.Many2One('currency.currency', "Currency", readonly=True)
    lines = fields.Many2Many('account.move.line', None, None, 'Lines',
        domain=[
            ('account', '=', Eval('account', -1)),
            ('party', '=', Eval('party', -1)),
            ('reconciliation', '=', None),
            ['OR',
                [
                    ('currency', '=', Eval('currency', -1)),
                    ('second_currency', '=', None),
                    ],
                ('second_currency', '=', Eval('currency', -1)),
                ],
            ])

    _write_off_states = {
        'required': Bool(Eval('write_off_amount', 0)),
        'invisible': ~Eval('write_off_amount', 0),
        }

    write_off_amount = Monetary(
        "Amount", currency='currency', digits='currency', readonly=True,
        states=_write_off_states)
    write_off = fields.Many2One(
        'account.move.reconcile.write_off', "Write Off",
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        states=_write_off_states)
    date = fields.Date('Date', states=_write_off_states)
    description = fields.Char('Description',
        states={
            'invisible': _write_off_states['invisible'],
            })

    @fields.depends('lines', 'currency', 'company')
    def on_change_lines(self):
        amount = Decimal(0)
        if self.currency:
            for line in self.lines:
                if line.second_currency == self.currency:
                    amount += (
                        line.amount_second_currency or 0)
                elif line.currency == self.currency:
                    amount += (
                        (line.debit or 0) - (line.credit or 0))
            amount = self.currency.round(amount)
        self.write_off_amount = amount


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
        Line = pool.get('account.move.line')
        Move = pool.get('account.move')
        Warning = pool.get('res.user.warning')
        Unreconcile = pool.get('account.move.unreconcile_lines', type='wizard')
        transaction = Transaction()

        moves = self.records
        moves_w_delegation = {
            m: [ml for ml in m.lines
                if ml.reconciliation and ml.reconciliation.delegate_to]
            for m in moves}
        if any(dml for dml in moves_w_delegation.values()):
            names = ', '.join(m.rec_name for m in
                islice(moves_w_delegation.keys(), None, 5))
            if len(moves_w_delegation) > 5:
                names += '...'
            key = Warning.format('cancel_delegated', moves_w_delegation)
            if Warning.check(key):
                raise CancelDelegatedWarning(
                    key, gettext(
                        'account.msg_cancel_line_delegated', moves=names))

        to_post = []
        for move in moves:
            if moves_w_delegation.get(move):
                with transaction.set_context(_skip_warnings=True):
                    Unreconcile.make_unreconciliation(moves_w_delegation[move])
            default = self.default_cancel(move)
            cancel_move = move.cancel(
                default=default, reversal=self.default.reversal)
            if move.state == 'posted':
                to_post.append(cancel_move)
            to_reconcile = defaultdict(list)
            for line in move.lines + cancel_move.lines:
                if line.account.reconcile:
                    to_reconcile[(line.account, line.party)].append(line)
            for lines in to_reconcile.values():
                Line.reconcile(lines)
        if to_post:
            Move.post(to_post)
        return 'end'


class CancelMovesDefault(ModelView):
    'Cancel Moves'
    __name__ = 'account.move.cancel.default'
    description = fields.Char('Description')
    reversal = fields.Boolean(
        "Reversal",
        help="Reverse debit and credit.")

    @classmethod
    def default_reversal(cls):
        return True


class GroupLines(Wizard):
    "Group Lines"
    __name__ = 'account.move.line.group'
    start = StateView('account.move.line.group.start',
        'account.move_line_group_start_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Group", 'group', 'tryton-ok', default=True),
            ])
    group = StateAction('account.act_move_form_grouping')

    def do_group(self, action):
        move, balance_line = self._group_lines(self.records)
        if all(l.move.state == 'posted' for l in self.records):
            move.post()
        return action, {'res_id': move.id}

    def _group_lines(self, lines, date=None):
        move, balance_line = self.group_lines(lines, self.start.journal, date)
        move.description = self.start.description
        move.save()
        return move, balance_line

    @classmethod
    def group_lines(cls, lines, journal, date=None):
        pool = Pool()
        Line = pool.get('account.move.line')

        grouping = cls.grouping(lines)

        move, balance_line = cls.get_move(lines, grouping, journal, date)
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

        return move, balance_line

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

    @classmethod
    def get_move(cls, lines, grouping, journal, date=None):
        pool = Pool()
        Date = pool.get('ir.date')
        Move = pool.get('account.move')
        Period = pool.get('account.period')
        Line = pool.get('account.move.line')

        company = grouping['company']
        if not date:
            with Transaction().set_context(company=company.id):
                date = Date.today()
        period = Period.find(company, date=date)

        move = Move()
        move.company = company
        move.date = date
        move.period = period
        move.journal = journal

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
            cline = cls._counterpart_line(line)
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

    @classmethod
    def _counterpart_line(cls, line):
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


class RescheduleLines(Wizard):
    "Reschedule Lines"
    __name__ = 'account.move.line.reschedule'
    start = StateView('account.move.line.reschedule.start',
        'account.move_line_reschedule_start_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Preview", 'preview', 'tryton-ok',
                validate=False, default=True),
            ])
    preview = StateView('account.move.line.reschedule.preview',
        'account.move_line_reschedule_preview_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Reschedule", 'reschedule', 'tryton-ok', default=True),
            ])
    reschedule = StateAction('account.act_move_form_rescheduling')

    def get_origin(self):
        try:
            origin, = {r.move.origin for r in self.records}
        except ValueError:
            raise RescheduleLineError(
                gettext('account.msg_reschedule_line_same_origins'))
        return origin

    @classmethod
    def get_currency(cls, lines):
        try:
            currency, = {l.amount_currency for l in lines}
        except ValueError:
            raise RescheduleLineError(
                gettext('account.msg_reschedule_line_same_currency'))
        return currency

    @classmethod
    def get_account(cls, lines):
        try:
            account, = {l.account for l in lines}
        except ValueError:
            raise RescheduleLineError(
                gettext('account.msg_reschedule_line_same_account'))
        return account

    @classmethod
    def get_party(cls, lines):
        try:
            party, = {l.party for l in lines}
        except ValueError:
            raise RescheduleLineError(
                gettext('account.msg_reschedule_line_same_party'))
        return party

    @classmethod
    def get_total_amount(cls, lines):
        return sum(l.amount for l in lines)

    @classmethod
    def get_balance(cls, lines):
        return sum(l.debit - l.credit for l in lines)

    def default_start(self, fields):
        values = {}
        self.get_origin()
        self.get_account(self.records)
        currency = self.get_currency(self.records)
        values['currency'] = currency.id
        values['total_amount'] = self.get_total_amount(self.records)
        return values

    def default_preview(self, fields):
        values = {}
        currency = self.get_currency(self.records)
        try:
            journal, = {r.move.journal for r in self.records}
            values['journal'] = journal.id
        except ValueError:
            pass
        values['currency'] = currency.id
        if (self.start.start_date
                and self.start.interval
                and self.start.currency):
            remaining = self.start.total_amount
            date = self.start.start_date
            values['terms'] = terms = []
            if self.start.amount:
                interval = self.start.interval
                amount = self.start.amount.copy_sign(remaining)
                while remaining - amount > 0:
                    terms.append({
                            'date': date,
                            'amount': amount,
                            'currency': currency.id,
                            })
                    date = (
                        self.start.start_date + relativedelta(months=interval))
                    interval += self.start.interval
                    remaining -= amount
                if remaining:
                    terms.append({
                            'date': date,
                            'amount': remaining,
                            'currency': currency.id,
                            })
            elif self.start.number:
                amount = self.start.currency.round(
                    self.start.total_amount / self.start.number)
                for i in range(self.start.number):
                    terms.append({
                            'date': date + relativedelta(months=i),
                            'amount': amount,
                            'currency': currency.id,
                            })
                    remaining -= amount
                if remaining:
                    terms[-1]['amount'] += remaining
        return values

    def do_reschedule(self, action):
        move, balance_line = self.reschedule_lines(
            self.records, self.preview.journal, self.preview.terms)
        move.origin = self.get_origin()
        move.description = self.preview.description
        move.save()
        if all(l.move.state == 'posted' for l in self.records):
            move.post()
        action['res_id'] = [move.id]
        return action, {}

    @classmethod
    def _line_values(cls, lines):
        account = cls.get_account(lines)
        currency = cls.get_currency(lines)
        if currency == account.currency:
            currency = None
        return {
            'account': account,
            'second_currency': currency,
            'party': cls.get_party(lines),
            }

    @classmethod
    def reschedule_lines(cls, lines, journal, terms):
        pool = Pool()
        Lang = pool.get('ir.lang')
        Line = pool.get('account.move.line')

        total_amount = cls.get_total_amount(lines)
        amount = sum(t.amount for t in terms)
        if amount != total_amount:
            lang = Lang.get()
            currency = cls.get_currency(lines)
            raise RescheduleLineError(
                gettext('account.msg_reschedule_line_wrong_amount',
                    total_amount=lang.currency(total_amount, currency),
                    amount=lang.currency(amount, currency)))

        balance = cls.get_balance(lines)
        line_values = cls._line_values(lines)
        account = line_values['account']
        move, balance_line = cls.get_reschedule_move(
            amount, balance, journal, terms, **line_values)
        move.save()
        balance_line.move = move
        balance_line.save()

        if account.reconcile:
            Line.reconcile(lines + [balance_line])
        return move, balance_line

    @classmethod
    def get_reschedule_move(
            cls, amount, balance, journal, terms, account, date=None,
            **line_values):
        pool = Pool()
        Date = pool.get('ir.date')
        Line = pool.get('account.move.line')
        Move = pool.get('account.move')
        Period = pool.get('account.period')

        company = account.company
        if not date:
            with Transaction().set_context(company=company.id):
                date = Date.today()
        period = Period.find(company, date=date)

        move = Move()
        move.company = company
        move.date = date
        move.period = period
        move.journal = journal

        balance_line = Line(account=account, **line_values)
        if balance >= 0:
            balance_line.debit, balance_line.credit = 0, balance
        else:
            balance_line.debit, balance_line.credit = -balance, 0
        if balance_line.second_currency:
            balance_line.amount_second_currency = -amount

        remaining_balance = balance
        remaining_amount = amount
        lines = []
        for term in terms:
            line = Line(account=account, **line_values)
            line.maturity_date = term.date
            factor = term.amount / amount
            line_amount = account.currency.round(balance * factor)
            if balance >= 0:
                line.debit, line.credit = line_amount, 0
            else:
                line.debit, line.credit = 0, -line_amount
            remaining_balance -= line_amount
            if line.second_currency:
                line_amount_second_currency = line.second_currency.round(
                    amount * factor)
                line.amount_second_currency = line_amount_second_currency
                remaining_amount -= line_amount_second_currency
            lines.append(line)
        if remaining_balance:
            if line.debit:
                line.debit += remaining_balance
            else:
                line.credit += remaining_balance
        if remaining_amount and line.second_currency:
            line.amount_second_currency += remaining_amount
        move.lines = lines
        return move, balance_line


class RescheduleLinesStart(ModelView):
    "Reschedule Lines"
    __name__ = 'account.move.line.reschedule.start'
    start_date = fields.Date("Start Date", required=True)
    frequency = fields.Selection([
            ('monthly', "Monthly"),
            ('quarterly', "Quarterly"),
            ('other', "Other"),
            ], "Frequency", sort=False, required=True)
    interval = fields.Integer(
        "Interval", required=True,
        states={
            'invisible': Eval('frequency') != 'other',
            },
        help="The length of each period, in months.")
    amount = Monetary(
        "Amount", currency='currency', digits='currency',
        states={
            'required': ~Eval('number'),
            'invisible': Bool(Eval('number')),
            },
        domain=[If(Eval('amount'),
                If(Eval('total_amount', 0) > 0,
                    [
                        ('amount', '<=', Eval('total_amount', 0)),
                        ('amount', '>', 0),
                        ],
                    [
                        ('amount', '>=', Eval('total_amount', 0)),
                        ('amount', '<', 0),
                        ]),
                [])])
    number = fields.Integer(
        "Number",
        domain=[
            ('number', '>', 0),
            ],
        states={
            'required': ~Eval('amount'),
            'invisible': Bool(Eval('amount')),
            })

    total_amount = fields.Numeric("Total Amount", readonly=True)
    currency = fields.Many2One('currency.currency', "Currency", readonly=True)

    @classmethod
    def default_frequency(cls):
        return 'monthly'

    @classmethod
    def frequency_intervals(cls):
        return {
            'monthly': 1,
            'quarterly': 3,
            'other': None,
            }

    @fields.depends('frequency', 'interval')
    def on_change_frequency(self):
        if self.frequency:
            self.interval = self.frequency_intervals()[self.frequency]


class RescheduleLinesPreview(ModelView):
    "Reschedule Lines"
    __name__ = 'account.move.line.reschedule.preview'
    journal = fields.Many2One('account.journal', "Journal", required=True)
    description = fields.Char("Description")
    terms = fields.One2Many(
        'account.move.line.reschedule.term', None, "Terms",
        domain=[
            ('currency', '=', Eval('currency', -1)),
            ])
    currency = fields.Many2One('currency.currency', "Currency", readonly=True)


class RescheduleLinesTerm(ModelView):
    "Reschedule Lines"
    __name__ = 'account.move.line.reschedule.term'
    date = fields.Date("Date", required=True)
    amount = Monetary(
        "Amount", currency='currency', digits='currency', required=True)
    currency = fields.Many2One('currency.currency', "Currency", required=True)


class DelegateLines(Wizard):
    "Delegate Lines"
    __name__ = 'account.move.line.delegate'
    start = StateView(
        'account.move.line.delegate.start',
        'account.move_line_delegate_start_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Delegate", 'delegate', 'tryton-ok', default=True),
            ])
    delegate = StateAction('account.act_move_form_delegate')

    def default_start(self, fields):
        values = {}
        if 'journal' in fields:
            journals = {l.journal for l in self.records}
            if len(journals) == 1:
                journal, = journals
                values['journal'] = journal.id
        return values

    def do_delegate(self, action):
        move = self._delegate_lines(self.records, self.start.party)
        if all(l.move.state == 'posted' for l in self.records):
            move.post()
        return action, {'res_id': move.id}

    def _delegate_lines(self, lines, party, date=None):
        move = self.delegate_lines(lines, party, self.start.journal, date)
        move.description = self.start.description
        move.save()
        return move

    @classmethod
    def delegate_lines(cls, lines, party, journal, date=None):
        pool = Pool()
        Line = pool.get('account.move.line')

        move, counterpart, delegated = cls.get_move(
            lines, party, journal, date=date)
        move.save()
        Line.save(counterpart + delegated)
        for line, cline, dline in zip(lines, counterpart, delegated):
            Line.reconcile([line, cline], delegate_to=dline)
        return move

    @classmethod
    def get_move(cls, lines, party, journal, date=None):
        pool = Pool()
        Date = pool.get('ir.date')
        Move = pool.get('account.move')
        Period = pool.get('account.period')

        try:
            company, = {l.company for l in lines}
        except ValueError:
            raise DelegateLineError(
                gettext('account.msg_delegate_line_same_company'))

        try:
            origin, = {l.move.origin for l in lines}
        except ValueError:
            raise DelegateLineError(
                gettext('account.msg_delegate_line_same_origins'))

        if not date:
            with Transaction().set_context(company=company.id):
                date = Date.today()
        period = Period.find(company, date=date)

        move = Move()
        move.company = company
        move.date = date
        move.period = period
        move.journal = journal
        move.origin = origin

        counterpart = []
        delegated = []
        for line in lines:
            cline = cls.get_move_line(line)
            cline.move = move
            cline.debit, cline.credit = line.credit, line.debit
            if cline.amount_second_currency:
                cline.amount_second_currency *= -1
            counterpart.append(cline)
            dline = cls.get_move_line(line)
            dline.move = move
            dline.party = party
            delegated.append(dline)
        return move, counterpart, delegated

    @classmethod
    def get_move_line(cls, line):
        pool = Pool()
        Line = pool.get('account.move.line')

        new = Line()
        new.debit = line.debit
        new.credit = line.credit
        new.account = line.account
        new.origin = line
        new.description = line.description
        new.amount_second_currency = line.amount_second_currency
        new.second_currency = line.second_currency
        new.party = line.party
        new.maturity_date = line.maturity_date
        return new


class DelegateLinesStart(ModelView):
    "Delegate Lines"
    __name__ = 'account.move.line.delegate.start'

    journal = fields.Many2One('account.journal', "Journal", required=True)
    party = fields.Many2One('party.party', "Party", required=True)
    description = fields.Char("Description")


class GeneralJournal(Report):
    __name__ = 'account.move.general_journal'

    @classmethod
    def get_context(cls, records, header, data):
        pool = Pool()
        Company = pool.get('company.company')
        context = Transaction().context
        report_context = super().get_context(records, header, data)
        report_context['company'] = Company(context['company'])
        return report_context
