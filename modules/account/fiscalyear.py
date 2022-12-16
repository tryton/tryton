# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from dateutil.relativedelta import relativedelta
from trytond.model import ModelView, ModelSQL, Workflow, fields
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.tools import datetime_strftime
from trytond.pyson import Eval, If, PYSONEncoder
from trytond.transaction import Transaction
from trytond.pool import Pool

__all__ = ['FiscalYear', 'FiscalYearLine',
    'BalanceNonDeferralStart', 'BalanceNonDeferral']

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
            states=STATES, depends=DEPENDS)
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
    close_lines = fields.Many2Many('account.fiscalyear-account.move.line',
            'fiscalyear', 'line', 'Close Lines')
    icon = fields.Function(fields.Char("Icon"), 'get_icon')

    @classmethod
    def __setup__(cls):
        super(FiscalYear, cls).__setup__()
        cls._order.insert(0, ('start_date', 'ASC'))
        cls._error_messages.update({
                'change_post_move_sequence': ('You can not change the post '
                    'move sequence in fiscal year "%s".'),
                'no_fiscalyear_date': 'No fiscal year defined for "%s".',
                'fiscalyear_overlaps': ('Fiscal year "%(first)s" and '
                    '"%(second)s" overlap.'),
                'different_post_move_sequence': ('Fiscal year "%(first)s" and '
                    '"%(second)s" have the same post move sequence.'),
                'account_balance_not_zero': ('The balance of the account "%s" '
                    'must be zero.'),
                'close_error': ('You can not close fiscal year "%s" until you '
                    'close all previous fiscal years.'),
                'reopen_error': ('You can not reopen fiscal year "%s" until '
                    'you reopen all later fiscal years.'),
                })
        cls._transitions |= set((
                ('open', 'close'),
                ('close', 'locked'),
                ('close', 'open'),
                ))
        cls._buttons.update({
                'create_period': {
                    'invisible': ((Eval('state') != 'open')
                        | Eval('periods', [0])),
                    },
                'create_period_3': {
                    'invisible': ((Eval('state') != 'open')
                        | Eval('periods', [0])),
                    },
                'close': {
                    'invisible': Eval('state') != 'open',
                    },
                'reopen': {
                    'invisible': Eval('state') != 'close',
                    },
                'lock': {
                    'invisible': Eval('state') != 'close',
                    },
                })

    @staticmethod
    def default_state():
        return 'open'

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    def get_icon(self, name):
        return {
            'open': 'tryton-open',
            'close': 'tryton-close',
            'locked': 'tryton-readonly',
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
            self.raise_user_error('fiscalyear_overlaps', {
                    'first': self.rec_name,
                    'second': second.rec_name,
                    })

    def check_post_move_sequence(self):
        years = self.search([
                ('post_move_sequence', '=', self.post_move_sequence.id),
                ('id', '!=', self.id),
                ])
        if years:
            self.raise_user_error('different_post_move_sequence', {
                    'first': self.rec_name,
                    'second': years[0].rec_name,
                    })

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        for fiscalyears, values in zip(actions, actions):
            if values.get('post_move_sequence'):
                for fiscalyear in fiscalyears:
                    if (fiscalyear.post_move_sequence
                            and fiscalyear.post_move_sequence.id !=
                            values['post_move_sequence']):
                        cls.raise_user_error('change_post_move_sequence', (
                                fiscalyear.rec_name,))
        super(FiscalYear, cls).write(*args)

    @classmethod
    def delete(cls, fiscalyears):
        Period = Pool().get('account.period')
        Period.delete([p for f in fiscalyears for p in f.periods])
        super(FiscalYear, cls).delete(fiscalyears)

    @classmethod
    @ModelView.button
    def create_period(cls, fiscalyears, interval=1):
        '''
        Create periods for the fiscal years with month interval
        '''
        Period = Pool().get('account.period')
        to_create = []
        for fiscalyear in fiscalyears:
            period_start_date = fiscalyear.start_date
            while period_start_date < fiscalyear.end_date:
                period_end_date = period_start_date + \
                    relativedelta(months=interval - 1) + \
                    relativedelta(day=31)
                if period_end_date > fiscalyear.end_date:
                    period_end_date = fiscalyear.end_date
                name = datetime_strftime(period_start_date, '%Y-%m')
                if name != datetime_strftime(period_end_date, '%Y-%m'):
                    name += ' - ' + datetime_strftime(period_end_date, '%Y-%m')
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
    @ModelView.button
    def create_period_3(cls, fiscalyears):
        '''
        Create periods for the fiscal years with 3 months interval
        '''
        cls.create_period(fiscalyears, interval=3)

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
                language = Transaction().language
                languages = Lang.search([('code', '=', language)])
                if not languages:
                    languages = Lang.search([('code', '=', 'en')])
                language, = languages
                formatted = Lang.strftime(date, language.code, language.date)
                cls.raise_user_error('no_fiscalyear_date', (formatted,))
            else:
                return None
        return fiscalyears[0].id

    def get_deferral(self, account):
        'Computes deferrals for accounts'
        pool = Pool()
        Currency = pool.get('currency.currency')
        Deferral = pool.get('account.account.deferral')

        if account.kind == 'view':
            return
        if not account.deferral:
            if not Currency.is_zero(self.company.currency, account.balance):
                self.raise_user_error('account_balance_not_zero',
                        error_args=(account.rec_name,))
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
                cls.raise_user_error('close_error', (fiscalyear.rec_name,))

            periods = Period.search([
                    ('fiscalyear', '=', fiscalyear.id),
                    ])
            Period.close(periods)

            with Transaction().set_context(fiscalyear=fiscalyear.id,
                    date=None, cumulate=True):
                accounts = Account.search([
                        ('company', '=', fiscalyear.company.id),
                        ])
                deferrals += filter(None, (fiscalyear.get_deferral(a)
                        for a in accounts))
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
                cls.raise_user_error('reopen_error')

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


class FiscalYearLine(ModelSQL):
    'Fiscal Year - Move Line'
    __name__ = 'account.fiscalyear-account.move.line'
    _table = 'account_fiscalyear_line_rel'
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
            ondelete='CASCADE', select=True)
    line = fields.Many2One('account.move.line', 'Line', ondelete='RESTRICT',
            select=True, required=True)


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
            ('kind', '!=', 'view'),
            ('company', '=', Eval('company', -1)),
            ('deferral', '=', True),
            ],
        depends=['company'])
    debit_account = fields.Many2One('account.account', 'Debit Account',
        required=True,
        domain=[
            ('kind', '!=', 'view'),
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
                    ('kind', '!=', 'view'),
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
                ('origin', '=', str(self.start.fiscalyear)),
                ])
        return action, {}
