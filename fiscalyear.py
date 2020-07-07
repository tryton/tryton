# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from dateutil.relativedelta import relativedelta

from trytond.i18n import gettext
from trytond.model import ModelView, ModelSQL, Workflow, fields
from trytond.model.exceptions import AccessError
from trytond.pool import Pool
from trytond.pyson import Eval, If, PYSONEncoder
from trytond.rpc import RPC
from trytond.transaction import Transaction
from trytond.wizard import (
    Wizard, StateView, StateTransition, StateAction, Button)

from .exceptions import (FiscalYearNotFoundError, FiscalYearDatesError,
    FiscalYearSequenceError, FiscalYearCloseError, FiscalYearReOpenError)

STATES = {
    'readonly': Eval('state') != 'open',
}
DEPENDS = ['state']


class FiscalYear(Workflow, ModelSQL, ModelView):
    'Fiscal Year'
    __name__ = 'account.fiscalyear'
    name = fields.Char('Name', size=None, required=True, depends=DEPENDS)
    start_date = fields.Date('Starting Date', required=True, states=STATES,
        domain=[('start_date', '<=', Eval('end_date', None))],
        depends=DEPENDS + ['end_date'])
    end_date = fields.Date('Ending Date', required=True, states=STATES,
        domain=[('end_date', '>=', Eval('start_date', None))],
        depends=DEPENDS + ['start_date'])
    periods = fields.One2Many('account.period', 'fiscalyear', 'Periods',
        states=STATES,
        domain=[
            ('company', '=', Eval('company')),
            ],
        depends=DEPENDS + ['company'])
    state = fields.Selection([
            ('open', 'Open'),
            ('close', 'Close'),
            ('locked', 'Locked'),
            ], 'State', readonly=True, required=True)
    post_move_sequence = fields.Many2One('ir.sequence', 'Post Move Sequence',
            required=True, domain=[('code', '=', 'account.move'),
                ['OR',
                    ('company', '=', Eval('company')),
                    ('company', '=', None)
                ]],
            context={
                'code': 'account.move',
                'company': Eval('company'),
            },
            depends=['company'])
    company = fields.Many2One('company.company', 'Company', required=True,
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ], select=True)
    icon = fields.Function(fields.Char("Icon"), 'get_icon')

    @classmethod
    def __setup__(cls):
        super(FiscalYear, cls).__setup__()
        cls._order.insert(0, ('start_date', 'ASC'))
        cls._transitions |= set((
                ('open', 'close'),
                ('close', 'locked'),
                ('close', 'open'),
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
                    'invisible': Eval('state') != 'close',
                    'depends': ['state'],
                    },
                'lock': {
                    'invisible': Eval('state') != 'close',
                    'depends': ['state'],
                    },
                })
        cls.__rpc__.update({
                'create_period': RPC(readonly=False, instantiate=0),
                })

    @staticmethod
    def default_state():
        return 'open'

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    def get_icon(self, name):
        return {
            'open': 'tryton-account-open',
            'close': 'tryton-account-close',
            'locked': 'tryton-account-block',
            }.get(self.state)

    @classmethod
    def validate(cls, years):
        super(FiscalYear, cls).validate(years)
        for year in years:
            year.check_dates()
            year.check_post_move_sequence()

    def check_dates(self):
        transaction = Transaction()
        connection = transaction.connection
        transaction.database.lock(connection, self._table)
        cursor = connection.cursor()
        table = self.__table__()
        cursor.execute(*table.select(table.id,
                where=(((table.start_date <= self.start_date)
                        & (table.end_date >= self.start_date))
                    | ((table.start_date <= self.end_date)
                        & (table.end_date >= self.end_date))
                    | ((table.start_date >= self.start_date)
                        & (table.end_date <= self.end_date)))
                & (table.company == self.company.id)
                & (table.id != self.id)))
        second_id = cursor.fetchone()
        if second_id:
            second = self.__class__(second_id[0])
            raise FiscalYearDatesError(
                gettext('account.msg_fiscalyear_overlap',
                    first=self.rec_name,
                    second=second.rec_name))

    def check_post_move_sequence(self):
        years = self.search([
                ('post_move_sequence', '=', self.post_move_sequence.id),
                ('id', '!=', self.id),
                ])
        if years:
            raise FiscalYearSequenceError(
                gettext('account.msg_fiscalyear_different_post_move_sequence',
                    first=self.rec_name,
                    second=years[0].rec_name))

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

    @classmethod
    def delete(cls, fiscalyears):
        Period = Pool().get('account.period')
        Period.delete([p for f in fiscalyears for p in f.periods])
        super(FiscalYear, cls).delete(fiscalyears)

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
    def find(cls, company_id, date=None, exception=True):
        '''
        Return the fiscal year for the company_id
            at the date or the current date.
        If exception is set the function will raise an exception
            if any fiscal year is found.
        '''
        pool = Pool()
        Lang = pool.get('ir.lang')
        Date = pool.get('ir.date')

        if not date:
            date = Date.today()
        fiscalyears = cls.search([
            ('start_date', '<=', date),
            ('end_date', '>=', date),
            ('company', '=', company_id),
            ], order=[('start_date', 'DESC')], limit=1)
        if not fiscalyears:
            if exception:
                lang = Lang.get()
                raise FiscalYearNotFoundError(
                    gettext('account.msg_no_fiscalyear_date',
                        date=lang.strftime(date)))
            else:
                return None
        return fiscalyears[0].id

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
            deferral.amount_second_currency = account.amount_second_currency
            return deferral

    @classmethod
    @ModelView.button
    @Workflow.transition('close')
    def close(cls, fiscalyears):
        '''
        Close a fiscal year
        '''
        pool = Pool()
        Period = pool.get('account.period')
        Account = pool.get('account.account')
        Deferral = pool.get('account.account.deferral')
        transaction = Transaction()
        database = transaction.database
        connection = transaction.connection

        # Lock period to be sure no new period will be created in between.
        database.lock(connection, Period._table)

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
                    date=None, cumulate=True):
                accounts = Account.search([
                        ('company', '=', fiscalyear.company.id),
                        ])
                deferrals += [_f for _f in (fiscalyear.get_deferral(a)
                        for a in accounts) if _f]
        Deferral.save(deferrals)

    @classmethod
    @ModelView.button
    @Workflow.transition('open')
    def reopen(cls, fiscalyears):
        '''
        Re-open a fiscal year
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
    def lock(cls, fiscalyears):
        pool = Pool()
        Period = pool.get('account.period')
        periods = Period.search([
                ('fiscalyear', 'in', [f.id for f in fiscalyears]),
                ])
        Period.lock(periods)


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
            ])
    period = fields.Many2One('account.period', 'Period', required=True,
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear')),
            ('type', '=', 'adjustment'),
            ],
        depends=['fiscalyear'])
    credit_account = fields.Many2One('account.account', 'Credit Account',
        required=True,
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('company', '=', Eval('company', -1)),
            ('deferral', '=', True),
            ],
        depends=['company'])
    debit_account = fields.Many2One('account.account', 'Debit Account',
        required=True,
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('company', '=', Eval('company', -1)),
            ('deferral', '=', True),
            ],
        depends=['company'])

    @fields.depends('fiscalyear')
    def on_change_with_company(self, name=None):
        if self.fiscalyear:
            return self.fiscalyear.company.id


class BalanceNonDeferral(Wizard):
    'Balance Non-Deferral'
    __name__ = 'account.fiscalyear.balance_non_deferral'
    start = StateView('account.fiscalyear.balance_non_deferral.start',
        'account.fiscalyear_balance_non_deferral_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'balance', 'tryton-ok', default=True),
            ])
    balance = StateAction('account.act_move_line_form')

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
        self.create_move()
        action['pyson_domain'] = PYSONEncoder().encode([
                ('move.origin', '=', str(self.start.fiscalyear)),
                ])
        return action, {}


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
        depends=['frequency'],
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
            ('company', '=', Eval('company')),
            ],
        depends=['company'],
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
        periods = [p for p in self.start.previous_fiscalyear.periods
            if p.type == 'standard']
        months = month_delta(fiscalyear.end_date, fiscalyear.start_date) + 1
        interval = months / len(periods)
        end_day = max(p.end_date.day
            for p in self.start.previous_fiscalyear.periods
            if p.type == 'standard')
        if interval.is_integer():
            FiscalYear.create_period([fiscalyear], interval, end_day)
        return fiscalyear

    def do_create_(self, action):
        fiscalyear = self.create_fiscalyear()
        action['res_id'] = [fiscalyear.id]
        action['views'].reverse()
        return action, {}
