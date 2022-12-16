#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
'Fiscal Year'
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard
import mx.DateTime

STATES = {
    'readonly': "state == 'close'",
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
            required=True, domain=["('code', '=', 'account.move')",
                ['OR',
                    "('company', '=', company)",
                    "('company', '=', False)"]],
                    context="{'code': 'account.move', 'company': company}",
            depends=['company'])
    company = fields.Many2One('company.company', 'Company', required=True,
            domain=["('id', 'company' in context and '=' or '!=', " \
                    "context.get('company', 0))"])

    def __init__(self):
        super(FiscalYear, self).__init__()
        self._rpc.update({
            'create_period': True,
            'create_period_3': True,
            'close': True,
            'reopen': True,
        })
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

    def default_state(self, cursor, user, context=None):
        return 'open'

    def default_company(self, cursor, user, context=None):
        company_obj = self.pool.get('company.company')
        if context is None:
            context = {}
        if context.get('company'):
            return context['company']
        return False

    def check_dates(self, cursor, user, ids):
        for fiscalyear in self.browse(cursor, user, ids):
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

    def check_post_move_sequence(self, cursor, user, ids):
        for fiscalyear in self.browse(cursor, user, ids):
            if self.search(cursor, user, [
                ('post_move_sequence', '=', fiscalyear.post_move_sequence.id),
                ('id', '!=', fiscalyear.id),
                ]):
                return False
        return True

    def write(self, cursor, user, ids, vals, context=None):
        move_obj = self.pool.get('account.move')
        if vals.get('post_move_sequence'):
            for fiscalyear in self.browse(cursor, user, ids, context=context):
                if fiscalyear.post_move_sequence and \
                        fiscalyear.post_move_sequence.id != \
                        vals['post_move_sequence']:
                    self.raise_user_error(cursor, 'change_post_move_sequence',
                            context=context)
        vals = vals.copy()
        if 'periods' in vals:
            operator = ['delete', 'unlink_all', 'unlink', 'create', 'write',
                    'add', 'set']
            vals['periods'].sort(
                    lambda x, y: cmp(operator.index(x[0]), operator.index(y[0])))
        return super(FiscalYear, self).write(cursor, user, ids, vals,
                context=context)

    def delete(self, cursor, user, ids, context=None):
        period_obj = self.pool.get('account.period')

        period_ids = []
        for fiscalyear in self.browse(cursor, user, ids, context=context):
            period_ids.extend([x.id for x in fiscalyear.periods])
        period_obj.delete(cursor, user, period_ids, context=context)
        return super(FiscalYear, self).delete(cursor, user, ids,
                context=context)

    def create_period(self, cursor, user, ids, context=None, interval=1):
        '''
        Create periods for the fiscal years with month interval
        '''
        period_obj = self.pool.get('account.period')
        for fiscalyear in self.browse(cursor, user, ids, context=context):
            end_date = mx.DateTime.strptime(str(fiscalyear.end_date),
                    '%Y-%m-%d')
            period_start_date = mx.DateTime.strptime(str(fiscalyear.start_date),
                    '%Y-%m-%d')
            while period_start_date < end_date:
                period_end_date = period_start_date + \
                        mx.DateTime.RelativeDateTime(months=interval)
                period_end_date = mx.DateTime.DateTime(period_end_date.year,
                        period_end_date.month, 1) - \
                        mx.DateTime.RelativeDateTime(days=1)
                if period_end_date > end_date:
                    period_end_date = end_date
                name = period_start_date.strftime('%Y-%m')
                if name != period_end_date.strftime('%Y-%m'):
                    name += ' - ' + period_end_date.strftime('%Y-%m')
                period_obj.create(cursor, user, {
                    'name': name,
                    'start_date': period_start_date.strftime('%Y-%m-%d'),
                    'end_date': period_end_date.strftime('%Y-%m-%d'),
                    'fiscalyear': fiscalyear.id,
                    'post_move_sequence': fiscalyear.post_move_sequence.id,
                    'type': 'standard',
                    }, context=context)
                period_start_date = period_end_date + \
                        mx.DateTime.RelativeDateTime(days=1)
        return True

    def create_period_3(self, cursor, user, ids, context=None):
        '''
        Create periods for the fiscal years with 3 months interval
        '''
        return self.create_period(cursor, user, ids, context=context,
                interval=3)

    def find(self, cursor, user, company_id, date=None, exception=True,
            context=None):
        '''
        Return the fiscal year for the company_id
            at the date or the current date.
        If exception is set the function will raise an exception
            if any fiscal year is found.
        '''
        date_obj = self.pool.get('ir.date')

        if not date:
            date = date_obj.today(cursor, user, context=context)
        ids = self.search(cursor, user, [
            ('start_date', '<=', date),
            ('end_date', '>=', date),
            ('company', '=', company_id),
            ], order=[('start_date', 'DESC')], limit=1, context=context)
        if not ids:
            if exception:
                self.raise_user_error(cursor, 'no_fiscalyear_date',
                        context=context)
            else:
                return False
        return ids[0]

    def _process_account(self, cursor, user, account, fiscalyear, context=None):
        '''
        Process account for a fiscal year closed

        :param cursor: the database cursor
        :param user: the user id
        :param account: a BrowseRecord of the account
        :param fiscalyear: a BrowseRecord of the fiscal year closed
        :param context: the context
        '''
        currency_obj = self.pool.get('currency.currency')
        deferral_obj = self.pool.get('account.account.deferral')

        if account.kind == 'view':
            return
        if not account.deferral:
            if not currency_obj.is_zero(cursor, user,
                    fiscalyear.company.currency, account.balance):
                self.raise_user_error(cursor, 'account_balance_not_zero',
                        error_args=(account.rec_name,), context=context)
        else:
            deferral_obj.create(cursor, user, {
                'account': account.id,
                'fiscalyear': fiscalyear.id,
                'debit': account.debit,
                'credit': account.credit,
                }, context=context)

    def close(self, cursor, user, fiscalyear_id, context=None):
        '''
        Close a fiscal year

        :param cursor: the database cursor
        :param user: the user id
        :param fiscalyear_id: the fiscal year id
        :param context: the context
        '''
        period_obj = self.pool.get('account.period')
        account_obj = self.pool.get('account.account')

        if context is None:
            context = {}

        if isinstance(fiscalyear_id, list):
            fiscalyear_id = fiscalyear_id[0]

        fiscalyear = self.browse(cursor, user, fiscalyear_id, context=context)

        if self.search(cursor, user, [
            ('end_date', '<=', fiscalyear.start_date),
            ('state', '=', 'open'),
            ('company', '=', fiscalyear.company.id),
            ], context=context):
            self.raise_user_error(cursor, 'close_error', context=context)

        #First close the fiscalyear to be sure
        #it will not have new period created between.
        self.write(cursor, user, fiscalyear_id, {
            'state': 'close',
            }, context=context)
        period_ids = period_obj.search(cursor, user, [
            ('fiscalyear', '=', fiscalyear_id),
            ], context=context)
        period_obj.close(cursor, user, period_ids, context=context)

        ctx = context.copy()
        ctx['fiscalyear'] = fiscalyear_id
        if 'date' in context:
            del context['date']

        account_ids = account_obj.search(cursor, user, [
            ('company', '=', fiscalyear.company.id),
            ], context=ctx)
        for account in account_obj.browse(cursor, user, account_ids,
                context=ctx):
            self._process_account(cursor, user, account, fiscalyear,
                    context=context)

    def reopen(self, cursor, user, fiscalyear_id, context=None):
        '''
        Re-open a fiscal year

        :param cursor: the database cursor
        :param user: the user id
        :param fiscalyear_id: the fiscal year id
        :param context: the context
        '''
        deferral_obj = self.pool.get('account.account.deferral')

        if isinstance(fiscalyear_id, list):
            fiscalyear_id = fiscalyear_id[0]

        fiscalyear = self.browse(cursor, user, fiscalyear_id, context=context)

        if self.search(cursor, user, [
            ('start_date', '>=', fiscalyear.end_date),
            ('state', '=', 'close'),
            ('company', '=', fiscalyear.company.id),
            ], context=context):
            self.raise_user_error(cursor, 'reopen_error', context=context)

        deferral_ids = deferral_obj.search(cursor, user, [
            ('fiscalyear', '=', fiscalyear_id),
            ], context=context)
        deferral_obj.delete(cursor, user, deferral_ids, context=context)

        self.write(cursor, user, fiscalyear_id, {
            'state': 'open',
            }, context=context)

FiscalYear()


class CloseFiscalYearInit(ModelView):
    'Close Fiscal Year Init'
    _name = 'account.fiscalyear.close_fiscalyear.init'
    _description = __doc__
    close_fiscalyear = fields.Many2One('account.fiscalyear',
            'Fiscal Year to close',
            required=True,
            domain=["('state', '!=', 'close')"])

CloseFiscalYearInit()


class CloseFiscalYear(Wizard):
    'Close Fiscal Year'
    _name = 'account.fiscalyear.close_fiscalyear'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'account.fiscalyear.close_fiscalyear.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('close', 'Close', 'tryton-ok', True),
                ],
            },
        },
        'close': {
            'actions': ['_close'],
            'result': {
                'type': 'state',
                'state': 'end',
            },
        },
    }

    def _close(self, cursor, user, data, context=None):
        fiscalyear_obj = self.pool.get('account.fiscalyear')

        fiscalyear_obj.close(cursor, user, data['form']['close_fiscalyear'],
                context=context)
        return {}

CloseFiscalYear()
