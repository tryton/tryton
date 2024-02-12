# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from sql.aggregate import Sum

from trytond.i18n import gettext
from trytond.model import (
    DeactivableMixin, MatchMixin, ModelSQL, ModelView, Unique, Workflow,
    fields, sequence_ordered)
from trytond.model.exceptions import AccessError
from trytond.modules.company.model import (
    CompanyMultiValueMixin, CompanyValueMixin)
from trytond.modules.currency.fields import Monetary
from trytond.pool import Pool
from trytond.pyson import Bool, Eval, Id
from trytond.tools import (
    grouped_slice, is_full_text, lstrip_wildcard, reduce_ids)
from trytond.transaction import Transaction

STATES = {
    'readonly': Eval('state') == 'closed',
}


class Journal(
        DeactivableMixin, MatchMixin,
        sequence_ordered('matching_sequence', "Matching Sequence"),
        ModelSQL, ModelView, CompanyMultiValueMixin):
    'Journal'
    __name__ = 'account.journal'
    name = fields.Char('Name', size=None, required=True, translate=True)
    code = fields.Char('Code', size=None)
    type = fields.Selection([
            ('general', "General"),
            ('revenue', "Revenue"),
            ('expense', "Expense"),
            ('cash', "Cash"),
            ('situation', "Situation"),
            ('write-off', "Write-Off"),
            ], 'Type', required=True)
    sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Sequence",
            domain=[
                ('sequence_type', '=',
                    Id('account', 'sequence_type_account_journal')),
                ('company', 'in', [
                        Eval('context', {}).get('company', -1), None]),
                ],
            states={
                'required': Bool(Eval('context', {}).get('company', -1)),
                }))
    sequences = fields.One2Many(
        'account.journal.sequence', 'journal', "Sequences")
    debit = fields.Function(Monetary(
            "Debit", currency='currency', digits='currency'),
        'get_debit_credit_balance')
    credit = fields.Function(Monetary(
            "Credit", currency='currency', digits='currency'),
        'get_debit_credit_balance')
    balance = fields.Function(Monetary(
            "Balance", currency='currency', digits='currency'),
        'get_debit_credit_balance')

    currency = fields.Function(fields.Many2One(
            'currency.currency', "Currency"), 'get_currency')

    @classmethod
    def __setup__(cls):
        super(Journal, cls).__setup__()
        cls._order.insert(0, ('name', 'ASC'))

    @classmethod
    def default_sequence(cls, **pattern):
        return cls.multivalue_model('sequence').default_sequence()

    @classmethod
    def search_rec_name(cls, name, clause):
        _, operator, operand, *extra = clause
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        code_value = operand
        if operator.endswith('like') and is_full_text(operand):
            code_value = lstrip_wildcard(operand)
        return [bool_op,
            ('code', operator, code_value, *extra),
            (cls._rec_name, operator, operand, *extra),
            ]

    @classmethod
    def get_currency(cls, journals, name):
        pool = Pool()
        Company = pool.get('company.company')
        company_id = Transaction().context.get('company')
        if company_id:
            company = Company(company_id)
            currency_id = company.currency.id
        else:
            currency_id = None
        return dict.fromkeys([j.id for j in journals], currency_id)

    @classmethod
    def get_debit_credit_balance(cls, journals, names):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Move = pool.get('account.move')
        Account = pool.get('account.account')
        AccountType = pool.get('account.account.type')
        Company = pool.get('company.company')
        context = Transaction().context
        cursor = Transaction().connection.cursor()

        result = {}
        ids = [j.id for j in journals]
        for name in ['debit', 'credit', 'balance']:
            result[name] = dict.fromkeys(ids, 0)

        company_id = Transaction().context.get('company')
        if not company_id:
            return result
        company = Company(company_id)

        line = MoveLine.__table__()
        move = Move.__table__()
        account = Account.__table__()
        account_type = AccountType.__table__()
        where = ((move.date >= context.get('start_date'))
            & (move.date <= context.get('end_date'))
            & ~account_type.receivable
            & ~account_type.payable
            & (move.company == company.id))
        for sub_journals in grouped_slice(journals):
            sub_journals = list(sub_journals)
            red_sql = reduce_ids(move.journal, [j.id for j in sub_journals])
            query = line.join(move, 'LEFT', condition=line.move == move.id
                ).join(account, 'LEFT', condition=line.account == account.id
                ).join(account_type, 'LEFT',
                    condition=account.type == account_type.id
                ).select(move.journal, Sum(line.debit), Sum(line.credit),
                    where=where & red_sql,
                    group_by=move.journal)
            cursor.execute(*query)
            for journal_id, debit, credit in cursor:
                # SQLite uses float for SUM
                if not isinstance(debit, Decimal):
                    debit = Decimal(str(debit))
                if not isinstance(credit, Decimal):
                    credit = Decimal(str(credit))
                result['debit'][journal_id] = company.currency.round(debit)
                result['credit'][journal_id] = company.currency.round(credit)
                result['balance'][journal_id] = company.currency.round(
                    debit - credit)
        return result

    @classmethod
    def find(cls, pattern):
        for journal in cls.search(
                [],
                order=[
                    ('matching_sequence', 'ASC'),
                    ('id', 'ASC'),
                    ]):
            if journal.match(pattern):
                return journal

    @classmethod
    def write(cls, *args):
        pool = Pool()
        Move = pool.get('account.move')
        actions = iter(args)
        for journals, values in zip(actions, actions):
            if 'type' in values:
                for sub_journals in grouped_slice(journals):
                    moves = Move.search([
                            ('journal', 'in', [j.id for j in sub_journals]),
                            ('state', '=', 'posted')
                            ], order=[], limit=1)
                    if moves:
                        move, = moves
                        raise AccessError(gettext(
                                'account.msg_journal_account_moves',
                                journal=move.journal.rec_name))
        super().write(*args)


class JournalSequence(ModelSQL, CompanyValueMixin):
    "Journal Sequence"
    __name__ = 'account.journal.sequence'
    journal = fields.Many2One(
        'account.journal', "Journal", ondelete='CASCADE',
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    sequence = fields.Many2One(
        'ir.sequence', "Sequence",
        domain=[
            ('sequence_type', '=',
                Id('account', 'sequence_type_account_journal')),
            ('company', 'in', [Eval('company', -1), None]),
            ],
        depends={'company'})

    @classmethod
    def default_sequence(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id('account', 'sequence_account_journal')
        except KeyError:
            return None


class JournalCashContext(ModelView):
    'Journal Cash Context'
    __name__ = 'account.journal.open_cash.context'
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date', required=True)

    @classmethod
    def default_start_date(cls):
        return Pool().get('ir.date').today()
    default_end_date = default_start_date


class JournalPeriod(
        DeactivableMixin, Workflow, ModelSQL, ModelView):
    'Journal - Period'
    __name__ = 'account.journal.period'
    journal = fields.Many2One('account.journal', 'Journal', required=True,
            ondelete='CASCADE', states=STATES)
    period = fields.Many2One('account.period', 'Period', required=True,
            ondelete='CASCADE', states=STATES)
    icon = fields.Function(fields.Char('Icon'), 'get_icon')
    state = fields.Selection([
        ('open', 'Open'),
        ('closed', 'Closed'),
        ], 'State', readonly=True, required=True, sort=False)

    @classmethod
    def __setup__(cls):
        super(JournalPeriod, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('journal_period_uniq', Unique(t, t.journal, t.period),
                'account.msg_journal_period_unique'),
            ]
        cls._transitions |= set((
                ('open', 'closed'),
                ('closed', 'open'),
                ))
        cls._buttons.update({
                'close': {
                    'invisible': Eval('state') != 'open',
                    'depends': ['state'],
                    },
                'reopen': {
                    'invisible': Eval('state') != 'closed',
                    'depends': ['state'],
                    },
                })
        cls.active.states = STATES

    @classmethod
    def __register__(cls, module):
        cursor = Transaction().connection.cursor()
        t = cls.__table__()
        super().__register__(module)
        # Migration from 6.8: rename state close to closed
        cursor.execute(
            *t.update([t.state], ['closed'], where=t.state == 'close'))

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
        return {
            'open': 'tryton-account-open',
            'closed': 'tryton-account-close',
            }.get(self.state)

    @classmethod
    def _check(cls, periods):
        Move = Pool().get('account.move')
        for period in periods:
            moves = Move.search([
                    ('journal', '=', period.journal.id),
                    ('period', '=', period.period.id),
                    ], limit=1)
            if moves:
                raise AccessError(
                    gettext('account.msg_modify_delete_journal_period_moves',
                        journal_period=period.rec_name))

    @classmethod
    def create(cls, vlist):
        Period = Pool().get('account.period')
        for vals in vlist:
            if vals.get('period'):
                period = Period(vals['period'])
                if period.state != 'open':
                    raise AccessError(
                        gettext('account'
                            '.msg_create_journal_period_closed_period',
                            period=period.rec_name))
        return super(JournalPeriod, cls).create(vlist)

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        for journal_periods, values in zip(actions, actions):
            if (values != {'state': 'closed'}
                    and values != {'state': 'open'}):
                cls._check(journal_periods)
            if values.get('state') == 'open':
                for journal_period in journal_periods:
                    if journal_period.period.state != 'open':
                        raise AccessError(
                            gettext('account'
                                '.msg_open_journal_period_closed_period',
                                journal_period=journal_period.rec_name,
                                period=journal_period.period.rec_name))
        super(JournalPeriod, cls).write(*args)

    @classmethod
    def delete(cls, periods):
        cls._check(periods)
        super(JournalPeriod, cls).delete(periods)

    @classmethod
    @ModelView.button
    @Workflow.transition('closed')
    def close(cls, periods):
        '''
        Close journal - period
        '''
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('open')
    def reopen(cls, periods):
        "Open journal - period"
        pass
