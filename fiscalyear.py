#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
'Fiscal Year'

from trytond.osv import fields, OSV
from trytond.wizard import Wizard, WizardOSV
import mx.DateTime
import datetime
from decimal import Decimal

STATES = {
    'readonly': "state == 'close'",
}


class FiscalYear(OSV):
    'Fiscal Year'
    _name = 'account.fiscalyear'
    _description = __doc__

    name = fields.Char('Name', size=None, required=True)
    code = fields.Char('Code', size=None)
    start_date = fields.Date('Starting Date', required=True, states=STATES)
    end_date = fields.Date('Ending Date', required=True, states=STATES)
    periods = fields.One2Many('account.period', 'fiscalyear', 'Periods',
            states=STATES)
    state = fields.Selection([
        ('open', 'Open'),
        ('close', 'Close'),
        ], 'State', readonly=True, required=True)
    post_move_sequence = fields.Many2One('ir.sequence', 'Post Move Sequence',
            required=True, domain="[('code', '=', 'account.move')]")
    company = fields.Many2One('company.company', 'Company', required=True)

    def __init__(self):
        super(FiscalYear, self).__init__()
        self._rpc_allowed += [
            'create_period',
            'create_period_3',
        ]
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
            })

    def default_state(self, cursor, user, context=None):
        return 'open'

    def default_company(self, cursor, user, context=None):
        company_obj = self.pool.get('company.company')
        if context is None:
            context = {}
        if context.get('company'):
            return company_obj.name_get(cursor, user, context['company'],
                    context=context)[0]
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
            if cursor.rowcount:
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
        return super(FiscalYear, self).write(cursor, user, ids, vals,
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
                period_obj.create(cursor, user, {
                    'name': period_start_date.strftime('%Y-%m') + ' - ' + \
                            period_end_date.strftime('%Y-%m'),
                    'start_date': period_start_date.strftime('%Y-%m-%d'),
                    'end_date': period_end_date.strftime('%Y-%m-%d'),
                    'fiscalyear': fiscalyear.id,
                    'post_move_sequence': fiscalyear.post_move_sequence.id,
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
        if not date:
            date = datetime.date.today()
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

    def close(self, cursor, user, ids, context=None):
        period_obj = self.pool.get('account.period')
        #First close the fiscalyear to be sure
        #it will not have new period created between.
        self.write(cursor, user, ids, {
            'state': 'close',
            }, context=context)
        period_ids = period_obj.search(cursor, user, [
            ('fiscalyear', 'in', ids),
            ], context=context)
        period_obj.close(cursor, user, period_ids, context=context)

FiscalYear()


class CloseFiscalYearInit(WizardOSV):
    _name = 'account.fiscalyear.close_fiscalyear.init'
    close_fiscalyear = fields.Many2One('account.fiscalyear',
            'Fiscal Year to close',
            required=True,
            domain="[('state', '!=', 'close'), ('id', '!=', fiscalyear)]")
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
            required=True,
            domain="[('state', '!=', 'close'), ('id', '!=', close_fiscalyear)]",
            help='The fiscal year where the entries will be done.')
    period = fields.Many2One('account.period', 'Period',
            required=True,
            domain="[('fiscalyear', '=', fiscalyear), ('state', '!=', 'close')]",
            help='The period where the entries will be done.')
    journal = fields.Many2One('account.journal', 'Journal', required=True,
            domain=[('centralised', '=', True)],
            help='The journal whre the netries will be done.')
    entries_name = fields.Char('New entries name', size=None, required=True,
            help='The name for the new entries')

    def default_entries_name(self, cursor, user, context=None):
        return 'End of Fiscal Year'

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

    def __init__(self):
        super(CloseFiscalYear, self).__init__()
        self._error_messages.update({
            'diff_fiscalyear': 'The fiscal years must be different!',
            'period_in_fiscalyear': 'The period must be ' \
                    'in the selected fiscal year!',
            'centralised_journal': 'The journal must be centralised!',
            'journal_default_debit_credit_account': 'The journal must have ' \
                    'default debit/credit accounts!',
            })

    def _process_account(self, cursor, user, account, period, journal, name,
            fiscalyear_id, period_ids, context=None):
        '''
        Method to override to implement new close method
        '''
        currency_obj = self.pool.get('currency.currency')
        move_line_obj = self.pool.get('account.move.line')
        fiscalyear_obj = self.pool.get('account.fiscalyear')

        if account.type == 'view':
            return
        if account.close_method == 'none':
            return
        if account.close_method == 'balance':
            balance = account.debit - account.credit
            if not currency_obj.is_zero(cursor, user, account.currency,
                    balance):
                line_id = move_line_obj.create(cursor, user, {
                    'name': name,
                    'debit': balance > Decimal('0.0') \
                            and balance or Decimal('0.0'),
                    'credit': balance < Decimal('0.0') \
                            and - balance or Decimal('0.0'),
                    'account': account.id,
                    'journal': journal.id,
                    'period': period.id,
                    'date': period.start_date,
                    }, context=context)
                fiscalyear_obj.write(cursor, user, fiscalyear_id, {
                    'close_lines': [('add', line_id)],
                    }, context=context)
            return
        if account.close_method == 'detail':
            offset = 0
            limit = 1000
            while True:
                move_line_ids = move_line_obj.search(cursor, user, [
                    ('period', 'in', period_ids),
                    ('account', '=', account.id),
                    ], offset=offset, limit=limit, context=context)
                if not move_line_ids:
                    break
                for line_id in move_line_ids:
                    line_id = move_line_obj.copy(cursor, user, line_id,
                            default={
                            'journal': journal.id,
                            'period': period.id,
                            'date': period.start_date,
                            'tax_lines': False,
                            }, context=context)
                    fiscalyear_obj.write(cursor, user, fiscalyear_id, {
                        'close_lines': [('add', line_id)],
                        }, context=context)
                offset += limit
            return
        if account.close_method == 'unreconciled':
            offset = 0
            limit = 1000
            while True:
                move_line_ids = move_line_obj.search(cursor, user, [
                    ('period', 'in', period_ids),
                    ('account', '=', account.id),
                    ('reconciliation', '=', False),
                    ], offset=offset, limit=limit, context=context)
                if not move_line_ids:
                    break
                for line_id in move_line_ids:
                    line_id = move_line_obj.copy(cursor, user, line_id,
                            default={
                            'journal': journal.id,
                            'period': period.id,
                            'date': period.start_date,
                            'tax_lines': False,
                            }, context=context)
                    fiscalyear_obj.write(cursor, user, fiscalyear_id, {
                        'close_lines': [('add', line_id)],
                        }, context=context)
                offset += limit
            return

    def _close(self, cursor, user, data, context=None):
        fiscalyear_obj = self.pool.get('account.fiscalyear')
        period_obj = self.pool.get('account.period')
        journal_obj = self.pool.get('account.journal')
        move_line_obj = self.pool.get('account.move.line')
        account_obj = self.pool.get('account.account')

        if data['form']['close_fiscalyear'] == data['form']['fiscalyear']:
            self.raise_user_error(cursor, 'diff_fiscalyear',
                    context=context)

        period = period_obj.browse(cursor, user, data['form']['period'],
                context=context)
        if period.fiscalyear.id != data['form']['fiscalyear']:
            self.raise_user_error(cursor, 'period_in_fiscalyear',
                    context=context)

        journal = journal_obj.browse(cursor, user, data['form']['journal'],
                context=context)
        if not journal.centralised:
            self.raise_user_error(cursor, 'centralised_journal',
                    context=context)

        if not journal.credit_account or not journal.debit_account:
            self.raise_user_error(cursor,
                    'journal_default_debit_credit_account',
                    context=context)

        ctx = context.copy()
        ctx['fiscalyear'] = data['form']['close_fiscalyear']
        period_ids = period_obj.search(cursor, user, [
            ('fiscalyear', '=', data['form']['close_fiscalyear']),
            ], context=ctx)

        account_ids = account_obj.search(cursor, user, [], context=ctx)
        for account in account_obj.browse(cursor, user, account_ids,
                context=ctx):
            self._process_account(cursor, user, account, period, journal,
                    data['form']['entries_name'],
                    data['form']['close_fiscalyear'], period_ids, context=ctx)

        fiscalyear_obj.close(cursor, user, [data['form']['close_fiscalyear']],
                context=context)
        return {}

CloseFiscalYear()


class ReOpenFiscalYear(Wizard):
    'Re-Open Fiscal Year'
    _name = 'account.fiscalyear.reopen_fiscalyear'
    states = {
        'init': {
            'actions': ['_reopen'],
            'result': {
                'type': 'state',
                'state': 'end',
            },
        },
    }

    def _reopen(self, cursor, user, data, context=None):
        fiscalyear_obj = self.pool.get('account.fiscalyear')
        move_line_obj = self.pool.get('account.move.line')
        for fiscalyear in fiscalyear_obj.browse(cursor, user, data['ids'],
                context=context):
            if fiscalyear.state == 'close':
                line_ids = [x.id for x in fiscalyear.close_lines]
                move_line_obj.delete(cursor, user, line_ids, context=context)
        fiscalyear_obj.write(cursor, user, data['ids'], {
            'state': 'open',
            }, context=context)
        return {}

ReOpenFiscalYear()
