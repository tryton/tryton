# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from sql import Null
from sql.aggregate import Sum

from trytond.model import ModelView, ModelSQL, fields, Unique
from trytond.wizard import Wizard, StateTransition
from trytond import backend
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.tools import reduce_ids, grouped_slice

__all__ = ['JournalType', 'Journal',
    'JournalCashContext',
    'JournalPeriod', 'CloseJournalPeriod', 'ReOpenJournalPeriod']

STATES = {
    'readonly': Eval('state') == 'close',
}
DEPENDS = ['state']

_ICONS = {
    'open': 'tryton-open',
    'close': 'tryton-readonly',
}


class JournalType(ModelSQL, ModelView):
    'Journal Type'
    __name__ = 'account.journal.type'
    name = fields.Char('Name', size=None, required=True, translate=True)
    code = fields.Char('Code', size=None, required=True)

    @classmethod
    def __setup__(cls):
        super(JournalType, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.code), 'The code must be unique.'),
            ]
        cls._order.insert(0, ('code', 'ASC'))


class Journal(ModelSQL, ModelView):
    'Journal'
    __name__ = 'account.journal'
    name = fields.Char('Name', size=None, required=True, translate=True)
    code = fields.Char('Code', size=None)
    active = fields.Boolean('Active', select=True)
    type = fields.Selection('get_types', 'Type', required=True)
    sequence = fields.Property(fields.Many2One('ir.sequence', 'Sequence',
            domain=[('code', '=', 'account.journal')],
            context={'code': 'account.journal'},
            states={
                'required': Bool(Eval('context', {}).get('company', -1)),
                }))
    credit_account = fields.Property(fields.Many2One('account.account',
            'Default Credit Account', domain=[
                ('kind', '!=', 'view'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'required': ((Eval('type').in_(['cash', 'write-off']))
                    & (Eval('context', {}).get('company', -1) != -1)),
                'invisible': ~Eval('context', {}).get('company', -1),
                }, depends=['type']))
    debit_account = fields.Property(fields.Many2One('account.account',
            'Default Debit Account', domain=[
                ('kind', '!=', 'view'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'required': ((Eval('type').in_(['cash', 'write-off']))
                    & (Eval('context', {}).get('company', -1) != -1)),
                'invisible': ~Eval('context', {}).get('company', -1),
                }, depends=['type']))
    debit = fields.Function(fields.Numeric('Debit',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_debit_credit_balance')
    credit = fields.Function(fields.Numeric('Credit',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_debit_credit_balance')
    balance = fields.Function(fields.Numeric('Balance',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_debit_credit_balance')
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'get_currency_digits')

    @classmethod
    def __setup__(cls):
        super(Journal, cls).__setup__()
        cls._order.insert(0, ('name', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        super(Journal, cls).__register__(module_name)
        cursor = Transaction().connection.cursor()
        table = TableHandler(cls, module_name)

        # Migration from 1.0 sequence Many2One change into Property
        if table.column_exist('sequence'):
            Property = Pool().get('ir.property')
            sql_table = cls.__table__()
            cursor.execute(*sql_table.select(sql_table.id, sql_table.sequence))
            for journal_id, sequence_id in cursor.fetchall():
                Property.set('sequence', cls._name,
                        journal_id, (sequence_id and
                            'ir.sequence,' + str(sequence_id) or False))
            table.drop_column('sequence', exception=True)

    @staticmethod
    def default_active():
        return True

    @staticmethod
    def default_sequence():
        return None

    @staticmethod
    def get_types():
        Type = Pool().get('account.journal.type')
        types = Type.search([])
        return [(x.code, x.name) for x in types]

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('code',) + tuple(clause[1:]),
            (cls._rec_name,) + tuple(clause[1:]),
            ]

    @classmethod
    def get_currency_digits(cls, journals, name):
        pool = Pool()
        Company = pool.get('company.company')
        company_id = Transaction().context.get('company')
        if company_id:
            company = Company(company_id)
            digits = company.currency.digits
        else:
            digits = 2
        return dict.fromkeys([j.id for j in journals], digits)

    @classmethod
    def get_debit_credit_balance(cls, journals, names):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Move = pool.get('account.move')
        context = Transaction().context
        cursor = Transaction().connection.cursor()

        result = {}
        ids = [j.id for j in journals]
        for name in ['debit', 'credit', 'balance']:
            result[name] = dict.fromkeys(ids, 0)

        line = MoveLine.__table__()
        move = Move.__table__()
        where = ((move.date >= context['start_date'])
            & (move.date <= context['end_date']))
        for sub_journals in grouped_slice(journals):
            sub_journals = list(sub_journals)
            red_sql = reduce_ids(move.journal, [j.id for j in sub_journals])
            accounts = None
            for journal in sub_journals:
                credit_account = (journal.credit_account.id
                    if journal.credit_account else None)
                debit_account = (journal.debit_account.id
                    if journal.debit_account else None)
                clause = ((move.journal == journal.id)
                    & (((line.credit != Null)
                            & (line.account == credit_account))
                        | ((line.debit != Null)
                            & (line.account == debit_account))))
                if accounts is None:
                    accounts = clause
                else:
                    accounts |= clause

            query = line.join(move, 'LEFT', condition=line.move == move.id
                ).select(move.journal, Sum(line.debit), Sum(line.credit),
                    where=where & red_sql & accounts,
                    group_by=move.journal)
            cursor.execute(*query)
            for journal_id, debit, credit in cursor.fetchall():
                # SQLite uses float for SUM
                if not isinstance(debit, Decimal):
                    debit = Decimal(str(debit))
                if not isinstance(credit, Decimal):
                    credit = Decimal(str(credit))
                result['debit'][journal_id] = debit
                result['credit'][journal_id] = credit
                result['balance'][journal_id] = debit - credit
        return result


class JournalCashContext(ModelView):
    'Journal Cash Context'
    __name__ = 'account.journal.open_cash.context'
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date', required=True)

    @classmethod
    def default_start_date(cls):
        return Pool().get('ir.date').today()
    default_end_date = default_start_date


class JournalPeriod(ModelSQL, ModelView):
    'Journal - Period'
    __name__ = 'account.journal.period'
    journal = fields.Many2One('account.journal', 'Journal', required=True,
            ondelete='CASCADE', states=STATES, depends=DEPENDS)
    period = fields.Many2One('account.period', 'Period', required=True,
            ondelete='CASCADE', states=STATES, depends=DEPENDS)
    icon = fields.Function(fields.Char('Icon'), 'get_icon')
    active = fields.Boolean('Active', select=True, states=STATES,
        depends=DEPENDS)
    state = fields.Selection([
        ('open', 'Open'),
        ('close', 'Close'),
        ], 'State', readonly=True, required=True)

    @classmethod
    def __setup__(cls):
        super(JournalPeriod, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('journal_period_uniq', Unique(t, t.journal, t.period),
                'You can only open one journal per period.'),
            ]

        cls._error_messages.update({
                'modify_del_journal_period': ('You can not modify/delete '
                        'journal - period "%s" because it has moves.'),
                'create_journal_period': ('You can not create a '
                        'journal - period on closed period "%s".'),
                'open_journal_period': ('You can not open '
                    'journal - period "%(journal_period)s" because period '
                    '"%(period)s" is closed.'),
                })

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')

        super(JournalPeriod, cls).__register__(module_name)

        table = TableHandler(cls, module_name)
        # Migration from 4.2: remove name column
        table.drop_column('name')

    @staticmethod
    def default_active():
        return True

    @staticmethod
    def default_state():
        return 'open'

    def get_rec_name(self, name):
        return '%s - %s' % (self.journal.rec_name, self.period.rec_name)

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
                [('journal.rec_name',) + tuple(clause[1:])],
                [('period.rec_name',) + tuple(clause[1:])],
                ]

    def get_icon(self, name):
        return _ICONS.get(self.state, '')

    @classmethod
    def _check(cls, periods):
        Move = Pool().get('account.move')
        for period in periods:
            moves = Move.search([
                    ('journal', '=', period.journal.id),
                    ('period', '=', period.period.id),
                    ], limit=1)
            if moves:
                cls.raise_user_error('modify_del_journal_period', (
                        period.rec_name,))

    @classmethod
    def create(cls, vlist):
        Period = Pool().get('account.period')
        for vals in vlist:
            if vals.get('period'):
                period = Period(vals['period'])
                if period.state == 'close':
                    cls.raise_user_error('create_journal_period', (
                            period.rec_name,))
        return super(JournalPeriod, cls).create(vlist)

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        for journal_periods, values in zip(actions, actions):
            if (values != {'state': 'close'}
                    and values != {'state': 'open'}):
                cls._check(journal_periods)
            if values.get('state') == 'open':
                for journal_period in journal_periods:
                    if journal_period.period.state == 'close':
                        cls.raise_user_error('open_journal_period', {
                                'journal_period': journal_period.rec_name,
                                'period': journal_period.period.rec_name,
                                })
        super(JournalPeriod, cls).write(*args)

    @classmethod
    def delete(cls, periods):
        cls._check(periods)
        super(JournalPeriod, cls).delete(periods)

    @classmethod
    def close(cls, periods):
        '''
        Close journal - period
        '''
        cls.write(periods, {
                'state': 'close',
                })

    @classmethod
    def open_(cls, periods):
        "Open journal - period"
        cls.write(periods, {
                'state': 'open',
                })


class CloseJournalPeriod(Wizard):
    'Close Journal - Period'
    __name__ = 'account.journal.period.close'
    start_state = 'close'
    close = StateTransition()

    def transition_close(self):
        JournalPeriod = Pool().get('account.journal.period')
        JournalPeriod.close(
            JournalPeriod.browse(Transaction().context['active_ids']))
        return 'end'


class ReOpenJournalPeriod(Wizard):
    'Re-Open Journal - Period'
    __name__ = 'account.journal.period.reopen'
    start_state = 'reopen'
    reopen = StateTransition()

    def transition_reopen(self):
        JournalPeriod = Pool().get('account.journal.period')
        JournalPeriod.open_(
            JournalPeriod.browse(Transaction().context['active_ids']))
        return 'end'
