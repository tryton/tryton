# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from dateutil.relativedelta import relativedelta
from sql import Null
from sql.conditionals import Case
from sql.operators import Equal, NotEqual

from trytond.cache import Cache
from trytond.i18n import gettext
from trytond.model import (
    Exclude, ModelSQL, ModelView, Unique, Workflow, fields)
from trytond.model.exceptions import AccessError
from trytond.pool import Pool
from trytond.pyson import Eval, Id
from trytond.rpc import RPC
from trytond.sql.functions import DateRange
from trytond.sql.operators import RangeOverlap
from trytond.transaction import Transaction
from trytond.wizard import (
    Button, StateAction, StateTransition, StateView, Wizard)

from .exceptions import (
    FiscalYearCloseError, FiscalYearNotFoundError, FiscalYearReOpenError)

STATES = {
    'readonly': Eval('state') != 'open',
}


class FiscalYear(Workflow, ModelSQL, ModelView):
    'Fiscal Year'
    __name__ = 'account.fiscalyear'
    name = fields.Char('Name', size=None, required=True)
    start_date = fields.Date('Starting Date', required=True, states=STATES,
        domain=[('start_date', '<=', Eval('end_date', None))])
    end_date = fields.Date('Ending Date', required=True, states=STATES,
        domain=[('end_date', '>=', Eval('start_date', None))])
    periods = fields.One2Many('account.period', 'fiscalyear', 'Periods',
        states=STATES,
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        order=[('start_date', 'ASC'), ('id', 'ASC')])
    state = fields.Selection([
            ('open', 'Open'),
            ('closed', 'Closed'),
            ('locked', 'Locked'),
            ], 'State', readonly=True, required=True, sort=False)
    post_move_sequence = fields.Many2One(
        'ir.sequence', "Post Move Sequence", required=True,
        domain=[
            ('sequence_type', '=',
                Id('account', 'sequence_type_account_move')),
            ('company', '=', Eval('company', -1)),
            ])
    company = fields.Many2One(
        'company.company', "Company", required=True)
    icon = fields.Function(fields.Char("Icon"), 'get_icon')
    _find_cache = Cache(__name__ + '.find', context=False)

    @classmethod
    def __setup__(cls):
        super(FiscalYear, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('dates_overlap',
                Exclude(t,
                    (t.company, Equal),
                    (DateRange(t.start_date, t.end_date, '[]'), RangeOverlap),
                    ),
                'account.msg_fiscalyear_overlap'),
            ('open_earlier',
                Exclude(t,
                    (t.company, Equal),
                    (DateRange(
                            Case(
                                (t.state == 'open', t.start_date), else_=Null),
                            t.end_date), RangeOverlap),
                    (Case((t.state == 'open', t.id), else_=-1), NotEqual)),
                'account.msg_open_fiscalyear_earlier'),
            ('post_move_sequence_unique', Unique(t, t.post_move_sequence),
                'account.msg_fiscalyear_post_move_sequence_unique'),
            ]
        cls._order.insert(0, ('start_date', 'DESC'))
        cls._transitions |= set((
                ('open', 'closed'),
                ('closed', 'locked'),
                ('closed', 'open'),
                ))
        cls._buttons.update({
                'create_periods': {
                    'invisible': ((Eval('state') != 'open')
                        | Eval('periods', [0])),
                    'depends': ['state'],
                    },
                'close': {
                    'invisible': Eval('state') != 'open',
                    'depends': ['state'],
                    },
                'reopen': {
                    'invisible': Eval('state') != 'closed',
                    'depends': ['state'],
                    },
                'lock_': {
                    'invisible': Eval('state') != 'closed',
                    'depends': ['state'],
                    },
                })
        cls.__rpc__.update({
                'create_period': RPC(readonly=False, instantiate=0),
                })

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

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    def get_icon(self, name):
        return {
            'open': 'tryton-account-open',
            'closed': 'tryton-account-close',
            'locked': 'tryton-account-block',
            }.get(self.state)

    @classmethod
    def validate_fields(cls, fiscalyears, field_names):
        super().validate_fields(fiscalyears, field_names)
        cls.check_period_dates(fiscalyears, field_names)

    @classmethod
    def check_period_dates(cls, fiscalyears, field_names=None):
        pool = Pool()
        Period = pool.get('account.period')
        if field_names and not (field_names & {'start_date', 'end_date'}):
            return
        periods = [p for f in fiscalyears for p in f.periods]
        Period.check_fiscalyear_dates(periods, field_names={'fiscalyear'})

    @classmethod
    def create(cls, vlist):
        fiscalyears = super().create(vlist)
        cls._find_cache.clear()
        return fiscalyears

    @classmethod
    def write(cls, *args):
        pool = Pool()
        Move = pool.get('account.move')
        actions = iter(args)
        for fiscalyears, values in zip(actions, actions):
            if values.get('post_move_sequence'):
                for fiscalyear in fiscalyears:
                    if (fiscalyear.post_move_sequence
                            and fiscalyear.post_move_sequence.id
                            != values['post_move_sequence']):
                        if Move.search([
                                    ('period.fiscalyear', '=', fiscalyear.id),
                                    ('state', '=', 'posted'),
                                    ]):
                            raise AccessError(
                                gettext('account.'
                                    'msg_change_fiscalyear_post_move_sequence',
                                    fiscalyear=fiscalyear.rec_name))
        super(FiscalYear, cls).write(*args)
        cls._find_cache.clear()

    @classmethod
    def delete(cls, fiscalyears):
        Period = Pool().get('account.period')
        Period.delete([p for f in fiscalyears for p in f.periods])
        super(FiscalYear, cls).delete(fiscalyears)
        cls._find_cache.clear()

    @classmethod
    def create_period(cls, fiscalyears, interval=1, end_day=31):
        '''
        Create periods for the fiscal years with month interval
        '''
        Period = Pool().get('account.period')
        to_create = []
        for fiscalyear in fiscalyears:
            period_start_date = fiscalyear.start_date
            while period_start_date < fiscalyear.end_date:
                month_offset = 1 if period_start_date.day < end_day else 0
                period_end_date = (period_start_date
                    + relativedelta(months=interval - month_offset)
                    + relativedelta(day=end_day))
                if period_end_date > fiscalyear.end_date:
                    period_end_date = fiscalyear.end_date
                name = period_start_date.strftime('%Y-%m')
                if name != period_end_date.strftime('%Y-%m'):
                    name += ' - ' + period_end_date.strftime('%Y-%m')
                to_create.append({
                    'name': name,
                    'start_date': period_start_date,
                    'end_date': period_end_date,
                    'fiscalyear': fiscalyear.id,
                    'type': 'standard',
                    })
                period_start_date = period_end_date + relativedelta(days=1)
        if to_create:
            Period.create(to_create)

    @classmethod
    @ModelView.button_action('account.act_create_periods')
    def create_periods(cls, fiscalyears):
        pass

    @classmethod
    def find(cls, company, date=None, test_state=True):
        '''
        Return the fiscal year for the company at the date or the current date
        or raise FiscalYearNotFoundError.
        If test_state is true, it searches on non-closed fiscal years
        '''
        pool = Pool()
        Lang = pool.get('ir.lang')
        Date = pool.get('ir.date')
        Company = pool.get('company.company')

        company_id = int(company) if company is not None else None
        if not date:
            with Transaction().set_context(company=company_id):
                date = Date.today()
        key = (company_id, date)
        fiscalyear = cls._find_cache.get(key, -1)
        if fiscalyear is not None and fiscalyear < 0:
            clause = [
                ('start_date', '<=', date),
                ('end_date', '>=', date),
                ('company', '=', company_id),
                ]
            fiscalyears = cls.search(
                clause, order=[('start_date', 'DESC')], limit=1)
            if fiscalyears:
                fiscalyear, = fiscalyears
            else:
                fiscalyear = None
            cls._find_cache.set(key, int(fiscalyear) if fiscalyear else None)
        elif fiscalyear is not None:
            fiscalyear = cls(fiscalyear)
        found = fiscalyear and (not test_state or fiscalyear.state == 'open')
        if not found:
            lang = Lang.get()
            if company is not None and not isinstance(company, Company):
                company = Company(company)
            if not fiscalyear:
                raise FiscalYearNotFoundError(
                    gettext('account.msg_no_fiscalyear_date',
                        date=lang.strftime(date),
                        company=company.rec_name if company else ''))
            else:
                raise FiscalYearNotFoundError(
                    gettext('account.msg_no_open_fiscalyear_date',
                        date=lang.strftime(date),
                        fiscalyear=fiscalyear.rec_name,
                        company=company.rec_name if company else ''))
        else:
            return fiscalyear

    def get_deferral(self, account):
        'Computes deferrals for accounts'
        pool = Pool()
        Currency = pool.get('currency.currency')
        Deferral = pool.get('account.account.deferral')

        if not account.type:
            return
        if not account.deferral:
            if not Currency.is_zero(self.company.currency, account.balance):
                raise FiscalYearCloseError(
                    gettext('account'
                        '.msg_close_fiscalyear_account_balance_not_zero',
                        account=account.rec_name))
        else:
            deferral = Deferral()
            deferral.account = account
            deferral.fiscalyear = self
            deferral.debit = account.debit
            deferral.credit = account.credit
            deferral.line_count = account.line_count
            deferral.amount_second_currency = account.amount_second_currency
            return deferral

    @classmethod
    @ModelView.button
    @Workflow.transition('closed')
    def close(cls, fiscalyears):
        '''
        Close a fiscal year
        '''
        pool = Pool()
        Period = pool.get('account.period')
        Account = pool.get('account.account')
        Deferral = pool.get('account.account.deferral')

        # Prevent create new fiscal year or period
        cls.lock()
        Period.lock()

        deferrals = []
        for fiscalyear in fiscalyears:
            if cls.search([
                        ('end_date', '<=', fiscalyear.start_date),
                        ('state', '=', 'open'),
                        ('company', '=', fiscalyear.company.id),
                        ]):
                raise FiscalYearCloseError(
                    gettext('account.msg_close_fiscalyear_earlier',
                        fiscalyear=fiscalyear.rec_name))

            periods = Period.search([
                    ('fiscalyear', '=', fiscalyear.id),
                    ])
            Period.close(periods)

            with Transaction().set_context(fiscalyear=fiscalyear.id,
                    date=None, cumulate=True, journal=None):
                accounts = Account.search([
                        ('company', '=', fiscalyear.company.id),
                        ])
                for account in accounts:
                    deferral = fiscalyear.get_deferral(account)
                    if deferral:
                        deferrals.append(deferral)
        Deferral.save(deferrals)

    @classmethod
    @ModelView.button
    @Workflow.transition('open')
    def reopen(cls, fiscalyears):
        '''
        Reopen a fiscal year
        '''
        Deferral = Pool().get('account.account.deferral')

        for fiscalyear in fiscalyears:
            if cls.search([
                        ('start_date', '>=', fiscalyear.end_date),
                        ('state', '!=', 'open'),
                        ('company', '=', fiscalyear.company.id),
                        ]):
                raise FiscalYearReOpenError(
                    gettext('account.msg_reopen_fiscalyear_later',
                        fiscalyear=fiscalyear.rec_name))

            deferrals = Deferral.search([
                ('fiscalyear', '=', fiscalyear.id),
                ])
            Deferral.delete(deferrals)

    @classmethod
    @ModelView.button
    @Workflow.transition('locked')
    def lock_(cls, fiscalyears):
        pool = Pool()
        Period = pool.get('account.period')
        periods = Period.search([
                ('fiscalyear', 'in', [f.id for f in fiscalyears]),
                ])
        Period.lock_(periods)


class BalanceNonDeferralStart(ModelView):
    'Balance Non-Deferral'
    __name__ = 'account.fiscalyear.balance_non_deferral.start'
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
        required=True, domain=[('state', '=', 'open')])
    company = fields.Function(fields.Many2One('company.company', 'Company'),
        'on_change_with_company')
    journal = fields.Many2One('account.journal', 'Journal', required=True,
        domain=[
            ('type', '=', 'situation'),
            ],
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    period = fields.Many2One('account.period', 'Period', required=True,
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear', -1)),
            ('type', '=', 'adjustment'),
            ])
    credit_account = fields.Many2One('account.account', 'Credit Account',
        required=True,
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('company', '=', Eval('company', -1)),
            ('deferral', '=', True),
            ])
    debit_account = fields.Many2One('account.account', 'Debit Account',
        required=True,
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('company', '=', Eval('company', -1)),
            ('deferral', '=', True),
            ])

    @fields.depends('fiscalyear')
    def on_change_with_company(self, name=None):
        return self.fiscalyear.company if self.fiscalyear else None


class BalanceNonDeferral(Wizard):
    'Balance Non-Deferral'
    __name__ = 'account.fiscalyear.balance_non_deferral'
    start = StateView('account.fiscalyear.balance_non_deferral.start',
        'account.fiscalyear_balance_non_deferral_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'balance', 'tryton-ok', default=True),
            ])
    balance = StateAction('account.act_move_form')

    def get_move_line(self, account):
        pool = Pool()
        Line = pool.get('account.move.line')
        # Don't use account.balance because we need the non-commulated balance
        balance = account.debit - account.credit
        if account.company.currency.is_zero(balance):
            return
        line = Line()
        line.account = account
        if balance >= 0:
            line.credit = abs(balance)
            line.debit = 0
        else:
            line.credit = 0
            line.debit = abs(balance)
        return line

    def get_counterpart_line(self, amount):
        pool = Pool()
        Line = pool.get('account.move.line')
        if self.start.fiscalyear.company.currency.is_zero(amount):
            return
        line = Line()
        if amount >= 0:
            line.credit = abs(amount)
            line.debit = 0
            line.account = self.start.credit_account
        else:
            line.credit = 0
            line.debit = abs(amount)
            line.account = self.start.debit_account
        return line

    def create_move(self):
        pool = Pool()
        Account = pool.get('account.account')
        Move = pool.get('account.move')

        with Transaction().set_context(fiscalyear=self.start.fiscalyear.id,
                date=None, cumulate=False):
            accounts = Account.search([
                    ('company', '=', self.start.fiscalyear.company.id),
                    ('deferral', '=', False),
                    ('type', '!=', None),
                    ('closed', '!=', True),
                    ])
        lines = []
        for account in accounts:
            line = self.get_move_line(account)
            if line:
                lines.append(line)
        if not lines:
            return
        amount = sum(l.debit - l.credit for l in lines)
        counter_part_line = self.get_counterpart_line(amount)
        if counter_part_line:
            lines.append(counter_part_line)

        move = Move()
        move.period = self.start.period
        move.journal = self.start.journal
        move.date = self.start.period.start_date
        move.origin = self.start.fiscalyear
        move.lines = lines
        move.save()
        return move

    def do_balance(self, action):
        move = self.create_move()
        if move:
            action['views'].reverse()
        return action, {'res_id': move.id if move else None}


class CreatePeriodsStart(ModelView):
    "Create Periods Start"
    __name__ = 'account.fiscalyear.create_periods.start'
    frequency = fields.Selection([
            ('monthly', "Monthly"),
            ('quarterly', "Quarterly"),
            ('other', "Other"),
            ], "Frequency", sort=False, required=True)
    interval = fields.Integer("Interval", required=True,
        states={
            'invisible': Eval('frequency') != 'other',
            },
        help="The length of each period, in months.")
    end_day = fields.Integer("End Day", required=True,
        help="The day of the month on which periods end.\n"
        "Months with fewer days will end on the last day.")

    @classmethod
    def default_frequency(cls):
        return 'monthly'

    @classmethod
    def default_end_day(cls):
        return 31

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


class CreatePeriods(Wizard):
    "Create Periods"
    __name__ = 'account.fiscalyear.create_periods'
    start = StateView('account.fiscalyear.create_periods.start',
        'account.fiscalyear_create_periods_start_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Create", 'create_periods', 'tryton-ok', default=True),
            ])
    create_periods = StateTransition()

    def transition_create_periods(self):
        self.model.create_period(
            [self.record], self.start.interval, self.start.end_day)
        return 'end'


def month_delta(d1, d2):
    month_offset = 1 if d1.day < d2.day else 0
    return (d1.year - d2.year) * 12 + d1.month - d2.month - month_offset


class RenewFiscalYearStart(ModelView):
    "Renew Fiscal Year Start"
    __name__ = 'account.fiscalyear.renew.start'
    name = fields.Char("Name", required=True)
    company = fields.Many2One('company.company', "Company", required=True)
    previous_fiscalyear = fields.Many2One(
        'account.fiscalyear', "Previous Fiscalyear", required=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        help="Used as reference for fiscalyear configuration.")
    start_date = fields.Date("Start Date", required=True)
    end_date = fields.Date("End Date", required=True)
    reset_sequences = fields.Boolean("Reset Sequences",
        help="If checked, new sequences will be created.")

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_previous_fiscalyear(cls):
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')
        fiscalyears = FiscalYear.search([
                ('company', '=', cls.default_company() or -1),
                ],
            order=[('end_date', 'DESC')], limit=1)
        if fiscalyears:
            fiscalyear, = fiscalyears
            return fiscalyear.id

    @classmethod
    def default_reset_sequences(cls):
        return True

    @fields.depends('previous_fiscalyear')
    def on_change_previous_fiscalyear(self):
        if self.previous_fiscalyear:
            fiscalyear = self.previous_fiscalyear
            months = month_delta(
                fiscalyear.end_date, fiscalyear.start_date) + 1
            self.start_date = fiscalyear.start_date + relativedelta(
                months=months, day=fiscalyear.start_date.day)
            self.end_date = fiscalyear.end_date + relativedelta(
                months=months, day=fiscalyear.end_date.day)
            self.name = fiscalyear.name.replace(
                str(fiscalyear.end_date.year),
                str(self.end_date.year)).replace(
                str(fiscalyear.start_date.year),
                str(self.start_date.year))


class RenewFiscalYear(Wizard):
    "Renew Fiscal Year"
    __name__ = 'account.fiscalyear.renew'
    start = StateView('account.fiscalyear.renew.start',
        'account.fiscalyear_renew_start_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Create", 'create_', 'tryton-ok', default=True),
            ])
    create_ = StateAction('account.act_fiscalyear_form')

    def fiscalyear_defaults(self):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        defaults = {
            'name': self.start.name,
            'start_date': self.start.start_date,
            'end_date': self.start.end_date,
            'periods': [],
            }
        previous_sequence = self.start.previous_fiscalyear.post_move_sequence
        sequence, = Sequence.copy([previous_sequence],
            default={
                'name': lambda data: data['name'].replace(
                    self.start.previous_fiscalyear.name,
                    self.start.name)
                })
        if self.start.reset_sequences:
            sequence.number_next = 1
        else:
            sequence.number_next = previous_sequence.number_next
        sequence.save()
        defaults['post_move_sequence'] = sequence.id
        return defaults

    def create_fiscalyear(self):
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')
        fiscalyear, = FiscalYear.copy(
            [self.start.previous_fiscalyear],
            default=self.fiscalyear_defaults())
        periods = [
            p for p in self.start.previous_fiscalyear.periods
            if p.type == 'standard']
        if periods:
            months = month_delta(fiscalyear.end_date, fiscalyear.start_date)
            months += 1
            interval = months / len(periods)
            end_day = max(
                p.end_date.day
                for p in self.start.previous_fiscalyear.periods
                if p.type == 'standard')
            if interval.is_integer():
                FiscalYear.create_period([fiscalyear], interval, end_day)
        return fiscalyear

    def do_create_(self, action):
        fiscalyear = self.create_fiscalyear()
        fiscalyear.save()
        action['views'].reverse()
        return action, {'res_id': fiscalyear.id}
