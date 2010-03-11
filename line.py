#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Line"
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard
from trytond.backend import TableHandler
from trytond.pyson import Eval, PYSONEncoder
import time


class Line(ModelSQL, ModelView):
    'Analytic Line'
    _name = 'analytic_account.line'
    _description = __doc__

    name = fields.Char('Name', required=True)
    debit = fields.Numeric('Debit', digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits'])
    credit = fields.Numeric('Credit', digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits'])
    currency = fields.Function(fields.Many2One('currency.currency', 'Currency',
        on_change_with=['move_line']), 'get_currency')
    currency_digits = fields.Function(fields.Integer('Currency Digits',
        on_change_with=['move_line']), 'get_currency_digits')
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

    def init(self, cursor, module_name):
        super(Line, self).init(cursor, module_name)
        table = TableHandler(cursor, self, module_name)

        # Migration from 1.2 currency has been changed in function field
        table.not_null_action('currency', action='remove')

    def default_date(self, cursor, user, context=None):
        date_obj = self.pool.get('ir.date')
        return date_obj.today(cursor, user, context=context)

    def default_active(self, cursor, user, context=None):
        return True

    def on_change_with_currency(self, cursor, user, ids, vals,
            context=None):
        move_line_obj = self.pool.get('account.move.line')
        if vals.get('move_line'):
            move_line = move_line_obj.browse(cursor, user, vals['move_line'],
                    context=context)
            return move_line.account.company.currency.id
        return False

    def get_currency(self, cursor, user, ids, name, context=None):
        res = {}
        for line in self.browse(cursor, user, ids, context=context):
            res[line.id] = line.move_line.account.company.currency.id
        return res

    def on_change_with_currency_digits(self, cursor, user, ids, vals,
            context=None):
        move_line_obj = self.pool.get('account.move.line')
        if vals.get('move_line'):
            move_line = move_line_obj.browse(cursor, user, vals['move_line'],
                    context=context)
            return move_line.account.company.currency.digits
        return 2

    def get_currency_digits(self, cursor, user, ids, name, context=None):
        res = {}
        for line in self.browse(cursor, user, ids, context=context):
            res[line.id] = line.move_line.account.company.currency.digits
        return res

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
            time.strptime(str(context['start_date']), '%Y-%m-%d')
            res += ' AND ' + obj + '.date >= date(\'' + \
                    str(context['start_date']) + '\')'
        if context.get('end_date'):
            # Check end_date
            time.strptime(str(context['end_date']), '%Y-%m-%d')
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


class MoveLine(ModelSQL, ModelView):
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

        act_window_id = model_data_obj.get_id(cursor, user, 'analytic_account',
                'act_line_form', context=context)
        res = act_window_obj.read(cursor, user, act_window_id, context=context)
        res['pyson_domain'] = [
            ('account', '=', data['id']),
        ]

        if context.get('start_date'):
            res['pyson_domain'].append(('date', '>=', context['start_date']))
        if context.get('end_date'):
            res['pyson_domain'].append(('date', '<=', context['end_date']))
        res['pyson_domain'] = PYSONEncoder().encode(res['pyson_domain'])
        return res

OpenAccount()
