# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from sql.aggregate import Sum

from trytond import backend
from trytond.i18n import gettext
from trytond.model import (
    ModelView, ModelSQL, Workflow, DeactivableMixin, fields, Unique)
from trytond.model.exceptions import AccessError
from trytond.pyson import Eval, Bool, Id
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.tools import reduce_ids, grouped_slice, lstrip_wildcard
from trytond.tools.multivalue import migrate_property
from trytond.modules.company.model import (
    CompanyMultiValueMixin, CompanyValueMixin)

STATES = {
    'readonly': Eval('state') == 'close',
}
DEPENDS = ['state']


class Journal(
        DeactivableMixin, ModelSQL, ModelView, CompanyMultiValueMixin):
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
    def default_sequence(cls, **pattern):
        return None

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        code_value = clause[2]
        if clause[1].endswith('like'):
            code_value = lstrip_wildcard(clause[2])
        return [bool_op,
            ('code', clause[1], code_value) + tuple(clause[3:]),
            (cls._rec_name,) + tuple(clause[1:]),
            ]

    @classmethod
    def get_currency_digits(cls, journals, name):
        pool = Pool()
        Company = pool.get('company.company')
        company_id = Transaction().context.get('company')
        if company_id is not None and company_id >= 0:
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


class JournalSequence(ModelSQL, CompanyValueMixin):
    "Journal Sequence"
    __name__ = 'account.journal.sequence'
    journal = fields.Many2One(
        'account.journal', "Journal", ondelete='CASCADE', select=True,
        context={
            'company': Eval('company', -1),
            },
        depends=['company'])
    sequence = fields.Many2One(
        'ir.sequence', "Sequence",
        domain=[
            ('sequence_type', '=',
                Id('account', 'sequence_type_account_journal')),
            ('company', 'in', [Eval('company', -1), None]),
            ],
        depends=['company'])

    @classmethod
    def __register__(cls, module_name):
        exist = backend.TableHandler.table_exist(cls._table)

        super(JournalSequence, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('sequence')
        value_names.append('sequence')
        fields.append('company')
        migrate_property(
            'account.journal', field_names, cls, value_names,
            parent='journal', fields=fields)


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
            ondelete='CASCADE', states=STATES, depends=DEPENDS)
    period = fields.Many2One('account.period', 'Period', required=True,
            ondelete='CASCADE', states=STATES, depends=DEPENDS)
    icon = fields.Function(fields.Char('Icon'), 'get_icon')
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
                'account.msg_journal_period_unique'),
            ]
        cls._transitions |= set((
                ('open', 'close'),
                ('close', 'open'),
                ))
        cls._buttons.update({
                'close': {
                    'invisible': Eval('state') != 'open',
                    'depends': ['state'],
                    },
                'reopen': {
                    'invisible': Eval('state') != 'close',
                    'depends': ['state'],
                    },
                })
        cls.active.states = STATES
        cls.active.depends = DEPENDS

    @classmethod
    def __register__(cls, module_name):
        super(JournalPeriod, cls).__register__(module_name)

        table = cls.__table_handler__(cls, module_name)
        # Migration from 4.2: remove name column
        table.drop_column('name')

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
            'close': 'tryton-account-close',
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
            if (values != {'state': 'close'}
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
    @Workflow.transition('close')
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
