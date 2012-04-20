#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from dateutil.relativedelta import relativedelta
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.tools import datetime_strftime
from trytond.pyson import Eval, If
from trytond.transaction import Transaction
from trytond.pool import Pool

STATES = {
    'readonly': Eval('state') == 'close',
}
DEPENDS = ['state']


class FiscalYear(ModelSQL, ModelView):
    'Fiscal Year'
    _name = 'account.fiscalyear'
    _description = __doc__

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

    def __init__(self):
        super(FiscalYear, self).__init__()
        self._constraints += [
            ('check_dates', 'fiscalyear_overlaps'),
            ('check_post_move_sequence', 'different_post_move_sequence'),
        ]
        self._order.insert(0, ('start_date', 'ASC'))
        self._error_messages.update({
            'change_post_move_sequence': 'You can not change ' \
                    'the post move sequence',
            'no_fiscalyear_date': 'No fiscal year defined for this date!',
            'fiscalyear_overlaps':
                'You can not have 2 fiscal years that overlaps!',
            'different_post_move_sequence':
                'You must have different post move sequence per fiscal year!',
            'account_balance_not_zero':
                'The balance of the account "%s" must be zero!',
            'close_error': 'You can not close a fiscal year until ' \
                    'there is older fiscal year opened!',
            'reopen_error': 'You can not reopen a fiscal year until ' \
                    'there is more recent fiscal year closed!',
            })
        self._buttons.update({
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

    def default_state(self):
        return 'open'

    def default_company(self):
        return Transaction().context.get('company')

    def check_dates(self, ids):
        cursor = Transaction().cursor
        for fiscalyear in self.browse(ids):
            cursor.execute('SELECT id ' \
                    'FROM ' + self._table + ' ' \
                    'WHERE ((start_date <= %s AND end_date >= %s) ' \
                            'OR (start_date <= %s AND end_date >= %s) ' \
                            'OR (start_date >= %s AND end_date <= %s)) ' \
                        'AND company = %s ' \
                        'AND id != %s',
                    (fiscalyear.start_date, fiscalyear.start_date,
                        fiscalyear.end_date, fiscalyear.end_date,
                        fiscalyear.start_date, fiscalyear.end_date,
                        fiscalyear.company.id, fiscalyear.id))
            if cursor.fetchone():
                return False
        return True

    def check_post_move_sequence(self, ids):
        for fiscalyear in self.browse(ids):
            if self.search([
                ('post_move_sequence', '=', fiscalyear.post_move_sequence.id),
                ('id', '!=', fiscalyear.id),
                ]):
                return False
        return True

    def write(self, ids, vals):
        if vals.get('post_move_sequence'):
            for fiscalyear in self.browse(ids):
                if fiscalyear.post_move_sequence and \
                        fiscalyear.post_move_sequence.id != \
                        vals['post_move_sequence']:
                    self.raise_user_error('change_post_move_sequence')
        vals = vals.copy()
        if 'periods' in vals:
            operator = ['delete', 'unlink_all', 'unlink', 'create', 'write',
                    'add', 'set']
            vals['periods'].sort(
                lambda x, y: cmp(operator.index(x[0]), operator.index(y[0])))
        return super(FiscalYear, self).write(ids, vals)

    def delete(self, ids):
        period_obj = Pool().get('account.period')

        period_ids = []
        for fiscalyear in self.browse(ids):
            period_ids.extend([x.id for x in fiscalyear.periods])
        period_obj.delete(period_ids)
        return super(FiscalYear, self).delete(ids)

    @ModelView.button
    def create_period(self, ids, interval=1):
        '''
        Create periods for the fiscal years with month interval
        '''
        period_obj = Pool().get('account.period')
        for fiscalyear in self.browse(ids):
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
                period_obj.create({
                    'name': name,
                    'start_date': period_start_date,
                    'end_date': period_end_date,
                    'fiscalyear': fiscalyear.id,
                    'post_move_sequence': fiscalyear.post_move_sequence.id,
                    'type': 'standard',
                    })
                period_start_date = period_end_date + relativedelta(days=1)
        return True

    @ModelView.button
    def create_period_3(self, ids):
        '''
        Create periods for the fiscal years with 3 months interval
        '''
        return self.create_period(ids, interval=3)

    def find(self, company_id, date=None, exception=True):
        '''
        Return the fiscal year for the company_id
            at the date or the current date.
        If exception is set the function will raise an exception
            if any fiscal year is found.
        '''
        date_obj = Pool().get('ir.date')

        if not date:
            date = date_obj.today()
        ids = self.search([
            ('start_date', '<=', date),
            ('end_date', '>=', date),
            ('company', '=', company_id),
            ], order=[('start_date', 'DESC')], limit=1)
        if not ids:
            if exception:
                self.raise_user_error('no_fiscalyear_date')
            else:
                return None
        return ids[0]

    def _process_account(self, account, fiscalyear):
        '''
        Process account for a fiscal year closed

        :param account: a BrowseRecord of the account
        :param fiscalyear: a BrowseRecord of the fiscal year closed
        '''
        currency_obj = Pool().get('currency.currency')
        deferral_obj = Pool().get('account.account.deferral')

        if account.kind == 'view':
            return
        if not account.deferral:
            if not currency_obj.is_zero(fiscalyear.company.currency,
                    account.balance):
                self.raise_user_error('account_balance_not_zero',
                        error_args=(account.rec_name,))
        else:
            deferral_obj.create({
                'account': account.id,
                'fiscalyear': fiscalyear.id,
                'debit': account.debit,
                'credit': account.credit,
                })

    @ModelView.button
    def close(self, ids):
        '''
        Close a fiscal year
        '''
        period_obj = Pool().get('account.period')
        account_obj = Pool().get('account.account')

        for fiscalyear in self.browse(ids):
            if self.search([
                ('end_date', '<=', fiscalyear.start_date),
                ('state', '=', 'open'),
                ('company', '=', fiscalyear.company.id),
                ]):
                self.raise_user_error('close_error')

            #First close the fiscalyear to be sure
            #it will not have new period created between.
            self.write(fiscalyear.id, {
                'state': 'close',
                })
            period_ids = period_obj.search([
                ('fiscalyear', '=', fiscalyear.id),
                ])
            period_obj.close(period_ids)

            with Transaction().set_context(fiscalyear=fiscalyear.id,
                    date=None):
                account_ids = account_obj.search([
                    ('company', '=', fiscalyear.company.id),
                    ])
                accounts = account_obj.browse(account_ids)
            for account in accounts:
                self._process_account(account, fiscalyear)

    @ModelView.button
    def reopen(self, ids):
        '''
        Re-open a fiscal year
        '''
        deferral_obj = Pool().get('account.account.deferral')

        for fiscalyear in self.browse(ids):
            if self.search([
                ('start_date', '>=', fiscalyear.end_date),
                ('state', '=', 'close'),
                ('company', '=', fiscalyear.company.id),
                ]):
                self.raise_user_error('reopen_error')

            deferral_ids = deferral_obj.search([
                ('fiscalyear', '=', fiscalyear.id),
                ])
            deferral_obj.delete(deferral_ids)

            self.write(fiscalyear.id, {
                'state': 'open',
                })

FiscalYear()


class CloseFiscalYearStart(ModelView):
    'Close Fiscal Year'
    _name = 'account.fiscalyear.close.start'
    _description = __doc__
    close_fiscalyear = fields.Many2One('account.fiscalyear',
            'Fiscal Year to close', required=True,
            domain=[('state', '!=', 'close')])

CloseFiscalYearStart()


class CloseFiscalYear(Wizard):
    'Close Fiscal Year'
    _name = 'account.fiscalyear.close'

    start = StateView('account.fiscalyear.close.start',
        'account.fiscalyear_close_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Close', 'close', 'tryton-ok', default=True),
            ])
    close = StateTransition()

    def transition_close(self, session):
        fiscalyear_obj = Pool().get('account.fiscalyear')
        fiscalyear_obj.close([session.start.close_fiscalyear.id])
        return 'end'

CloseFiscalYear()
