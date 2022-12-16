#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from dateutil.relativedelta import relativedelta
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.tools import datetime_strftime
from trytond.pyson import Eval, If
from trytond.transaction import Transaction
from trytond.pool import Pool

__all__ = ['FiscalYear', 'CloseFiscalYearStart', 'CloseFiscalYear']

STATES = {
    'readonly': Eval('state') == 'close',
}
DEPENDS = ['state']


class FiscalYear(ModelSQL, ModelView):
    'Fiscal Year'
    __name__ = 'account.fiscalyear'
    name = fields.Char('Name', size=None, required=True, depends=DEPENDS)
    code = fields.Char('Code', size=None)
    start_date = fields.Date('Starting Date', required=True, states=STATES,
            depends=DEPENDS)
    end_date = fields.Date('Ending Date', required=True, states=STATES,
            depends=DEPENDS)
    periods = fields.One2Many('account.period', 'fiscalyear', 'Periods',
            states=STATES, depends=DEPENDS)
    state = fields.Selection([
        ('open', 'Open'),
        ('close', 'Close'),
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
                Eval('context', {}).get('company', 0)),
            ], select=True)

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
                })

    @staticmethod
    def default_state():
        return 'open'

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @classmethod
    def validate(cls, years):
        super(FiscalYear, cls).validate(years)
        for year in years:
            year.check_dates()
            year.check_post_move_sequence()

    def check_dates(self):
        cursor = Transaction().cursor
        cursor.execute('SELECT id '
                'FROM ' + self._table + ' '
                'WHERE ((start_date <= %s AND end_date >= %s) '
                        'OR (start_date <= %s AND end_date >= %s) '
                        'OR (start_date >= %s AND end_date <= %s)) '
                    'AND company = %s '
                    'AND id != %s',
                (self.start_date, self.start_date,
                    self.end_date, self.end_date,
                    self.start_date, self.end_date,
                    self.company.id, self.id))
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
    def write(cls, fiscalyears, vals):
        if vals.get('post_move_sequence'):
            for fiscalyear in fiscalyears:
                if fiscalyear.post_move_sequence and \
                        fiscalyear.post_move_sequence.id != \
                        vals['post_move_sequence']:
                    cls.raise_user_error('change_post_move_sequence', (
                            fiscalyear.rec_name,))
        vals = vals.copy()
        if 'periods' in vals:
            operator = ['delete', 'unlink_all', 'unlink', 'create', 'write',
                    'add', 'set']
            vals['periods'].sort(
                lambda x, y: cmp(operator.index(x[0]), operator.index(y[0])))
        super(FiscalYear, cls).write(fiscalyears, vals)

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
                    languages = Lang.search([('code', '=', 'en_US')])
                language, = languages
                formatted = Lang.strftime(date, language.code, language.date)
                cls.raise_user_error('no_fiscalyear_date', (formatted,))
            else:
                return None
        return fiscalyears[0].id

    def _process_account(self, account):
        '''
        Process account for a fiscal year closed
        '''
        Currency = Pool().get('currency.currency')
        Deferral = Pool().get('account.account.deferral')

        if account.kind == 'view':
            return
        if not account.deferral:
            if not Currency.is_zero(self.company.currency, account.balance):
                self.raise_user_error('account_balance_not_zero',
                        error_args=(account.rec_name,))
        else:
            Deferral.create([{
                        'account': account.id,
                        'fiscalyear': self.id,
                        'debit': account.debit,
                        'credit': account.credit,
                        }])

    @classmethod
    @ModelView.button
    def close(cls, fiscalyears):
        '''
        Close a fiscal year
        '''
        pool = Pool()
        Period = pool.get('account.period')
        Account = pool.get('account.account')

        for fiscalyear in fiscalyears:
            if cls.search([
                        ('end_date', '<=', fiscalyear.start_date),
                        ('state', '=', 'open'),
                        ('company', '=', fiscalyear.company.id),
                        ]):
                cls.raise_user_error('close_error', (fiscalyear.rec_name,))

            #First close the fiscalyear to be sure
            #it will not have new period created between.
            cls.write([fiscalyear], {
                'state': 'close',
                })
            periods = Period.search([
                    ('fiscalyear', '=', fiscalyear.id),
                    ])
            Period.close(periods)

            with Transaction().set_context(fiscalyear=fiscalyear.id,
                    date=None, cumulate=True):
                accounts = Account.search([
                        ('company', '=', fiscalyear.company.id),
                        ])
            for account in accounts:
                fiscalyear._process_account(account)

    @classmethod
    @ModelView.button
    def reopen(cls, fiscalyears):
        '''
        Re-open a fiscal year
        '''
        Deferral = Pool().get('account.account.deferral')

        for fiscalyear in fiscalyears:
            if cls.search([
                        ('start_date', '>=', fiscalyear.end_date),
                        ('state', '=', 'close'),
                        ('company', '=', fiscalyear.company.id),
                        ]):
                cls.raise_user_error('reopen_error')

            deferrals = Deferral.search([
                ('fiscalyear', '=', fiscalyear.id),
                ])
            Deferral.delete(deferrals)

            cls.write([fiscalyear], {
                'state': 'open',
                })


class CloseFiscalYearStart(ModelView):
    'Close Fiscal Year'
    __name__ = 'account.fiscalyear.close.start'
    close_fiscalyear = fields.Many2One('account.fiscalyear',
            'Fiscal Year to close', required=True,
            domain=[('state', '!=', 'close')])


class CloseFiscalYear(Wizard):
    'Close Fiscal Year'
    __name__ = 'account.fiscalyear.close'
    start = StateView('account.fiscalyear.close.start',
        'account.fiscalyear_close_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Close', 'close', 'tryton-ok', default=True),
            ])
    close = StateTransition()

    def transition_close(self):
        Fiscalyear = Pool().get('account.fiscalyear')
        Fiscalyear.close([self.start.close_fiscalyear])
        return 'end'
