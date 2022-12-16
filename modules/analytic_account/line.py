#This file is part of Tryton.  The COPYRIGHT file at the top level
#of this repository contains the full copyright notices and license terms.
"Line"

from trytond.osv import fields, OSV
from trytond.wizard import Wizard
import mx.DateTime


class Line(OSV):
    'Analytic Line'
    _name = 'analytic_account.line'
    _description = __doc__

    name = fields.Char('Name', required=True)
    debit = fields.Numeric('Debit', digits=(16, 2))
    credit = fields.Numeric('Credit', digits=(16, 2))
    #TODO wrong field as currency comes from move_line
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    account = fields.Many2One('analytic_account.account', 'Account',
            required=True, select=1, domain=[('type', '!=', 'view')])
    move_line = fields.Many2One('account.move.line', 'Account Move Line',
            ondelete='CASCADE', required=True)
    journal = fields.Many2One('account.journal', 'Journal', required=True,
            select=1)
    date = fields.Date('Date', required=True)
    reference = fields.Char('Reference')
    party = fields.Many2One('party.party', 'Party')
    active = fields.Boolean('Active', select=2)

    def __init__(self):
        super(Line, self).__init__()
        self._sql_constraints += [
            ('credit_debit',
                'CHECK((credit * debit = 0.0) AND (credit + debit >= 0.0))',
                'Wrong credit/debit values!'),
        ]
        self._constraints += [
            ('check_account', 'line_on_view_inactive_account'),
        ]
        self._error_messages.update({
            'line_on_view_inactive_account': 'You can not create move line\n' \
                    'on view/inactive account!',
        })
        self._order.insert(0, ('date', 'ASC'))

    def default_currency(self, cursor, user, context=None):
        company_obj = self.pool.get('company.company')
        currency_obj = self.pool.get('currency.currency')
        if context is None:
            context = {}
        if context.get('company'):
            company = company_obj.browse(cursor, user, context['company'],
                    context=context)
            return currency_obj.name_get(cursor, user, company.currency.id,
                    context=context)[0]
        return False

    def default_date(self, cursor, user, context=None):
        date_obj = self.pool.get('ir.date')
        return date_obj.today(cursor, user, context=context)

    def default_active(self, cursor, user, context=None):
        return True

    def query_get(self, cursor, user, obj='l', context=None):
        '''
        Return SQL clause for analytic line depending of the context.
        obj is the SQL alias of the analytic_account_line in the query.
        '''
        if context is None:
            context = {}

        res = obj + '.active'
        if context.get('start_date'):
            # Check start_date
            mx.DateTime.strptime(str(context['start_date']), '%Y-%m-%d')
            res += ' AND ' + obj + '.date >= date(\'' + \
                    str(context['start_date']) + '\')'
        if context.get('end_date'):
            # Check end_date
            mx.DateTime.strptime(str(context['end_date']), '%Y-%m-%d')
            res += ' AND ' + obj + '.date <= date(\'' + \
                    str(context['end_date']) + '\')'
        return res

    def check_account(self, cursor, user, ids):
        for line in self.browse(cursor, user, ids):
            if line.account.type == 'view':
                return False
            if not line.account.active:
                return False
        return True

Line()


class MoveLine(OSV):
    _name = 'account.move.line'
    analytic_lines = fields.One2Many('analytic_account.line', 'move_line',
            'Analytic Lines')

MoveLine()


class OpenAccount(Wizard):
    'Open Account'
    _name = 'analytic_account.line.open_account'
    states = {
        'init': {
            'result': {
                'type': 'action',
                'action': '_action_open_account',
                'state': 'end',
            },
        },
    }

    def _action_open_account(self, cursor, user, data, context=None):
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')

        if context is None:
            context = {}

        model_data_ids = model_data_obj.search(cursor, user, [
            ('fs_id', '=', 'act_line_form'),
            ('module', '=', 'analytic_account'),
            ('inherit', '=', False),
            ], limit=1, context=context)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                context=context)
        res = act_window_obj.read(cursor, user, model_data.db_id, context=context)
        res['domain'] = [
            ('account', '=', data['id']),
        ]

        if context.get('start_date'):
            res['domain'].append(('date', '>=', context['start_date']))
        if context.get('end_date'):
            res['domain'].append(('date', '<=', context['end_date']))
        res['domain'] = str(res['domain'])
        return res

OpenAccount()
