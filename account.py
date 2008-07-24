#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
"Account"

from trytond.osv import fields, OSV
from trytond.wizard import Wizard, WizardOSV
from decimal import Decimal
import copy


class Account(OSV):
    'Analytic Account'
    _name = 'analytic_account.account'
    _description = __doc__

    name = fields.Char('Name', required=True, translate=True, select=1)
    complete_name = fields.Function('get_complete_name', type='char',
            string='Name')
    code = fields.Char('Code', select=1)
    active = fields.Boolean('Active', select=2)
    company = fields.Many2One('company.company', 'Company')
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    type = fields.Selection([
        ('root', 'Root'),
        ('view', 'View'),
        ('normal', 'Normal'),
        ], 'Type', required=True)
    root = fields.Many2One('analytic_account.account', 'Root', select=2,
            domain=[('parent', '=', False)],
            states={
                'invisible': "type == 'root'",
                'required': "type != 'root'",
            })
    parent = fields.Many2One('analytic_account.account', 'Parent', select=2,
            domain="[('parent', 'child_of', root)]",
            states={
                'invisible': "type == 'root'",
                'required': "type != 'root'",
            })
    childs = fields.One2Many('analytic_account.account', 'parent', 'Childs')
    #TODO fix digits depend of the currency
    balance = fields.Function('get_balance', digits=(16, 2), string='Balance')
    credit = fields.Function('get_credit_debit', digits=(16, 2), string='Credit')
    debit = fields.Function('get_credit_debit', digits=(16, 2), string='Debit')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('opened', 'Opened'),
        ('closed', 'Closed'),
        ], 'State', required=True)
    note = fields.Text('Note')
    display_balance = fields.Selection([
        ('debit-credit', 'Debit - Credit'),
        ('credit-debit', 'Credit - Debit'),
        ], 'Display Balance', required=True)
    mandatory = fields.Boolean('Mandatory', states={
        'invisible': "type != 'root'",
        })

    def __init__(self):
        super(Account, self).__init__()
        self._constraints += [
            ('check_recursion',
                'Error! You can not create recursive account.', ['parent']),
        ]
        self._order.insert(0, ('code', 'ASC'))

    def default_active(self, cursor, user, context=None):
        return True

    def default_company(self, cursor, user, context=None):
        company_obj = self.pool.get('company.company')
        if context is None:
            context = {}
        if context.get('company'):
            return company_obj.name_get(cursor, user, context['company'],
                    context=context)[0]
        return False

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

    def default_type(self, cursor, user, context=None):
        return 'normal'

    def default_state(self, cursor, user, context=None):
        return 'draft'

    def default_display_balance(self, cursor, user, context=None):
        return 'credit-debit'

    def default_mandatory(self, cursor, user, context=None):
        return False

    def get_complete_name(self, cursor, user, ids, name, arg, context=None):
        res = self.name_get(cursor, user, ids, context=context)
        return dict(res)

    def get_balance(self, cursor, user, ids, name, arg, context=None):
        res = {}
        line_obj = self.pool.get('analytic_account.line')
        currency_obj = self.pool.get('currency.currency')

        child_ids = self.search(cursor, user, [('parent', 'child_of', ids)],
                context=context)
        all_ids = {}.fromkeys(ids + child_ids).keys()

        id2account = {}
        accounts = self.browse(cursor, user, all_ids, context=context)
        for account in accounts:
            id2account[account.id] = account

        line_query = line_obj.query_get(cursor, user, context=context)
        cursor.execute('SELECT a.id, ' \
                    'SUM((COALESCE(l.debit, 0) - COALESCE(l.credit, 0))), ' \
                    'l.currency ' \
                'FROM analytic_account_account a ' \
                    'LEFT JOIN analytic_account_line l ' \
                    'ON (a.id = l.account) ' \
                'WHERE a.type != \'view\' ' \
                    'AND a.id IN (' + \
                        ','.join(['%s' for x in all_ids]) + ') ' \
                    'AND ' + line_query + ' ' \
                    'AND a.active ' \
                'GROUP BY a.id, l.currency', all_ids)
        account_sum = {}
        id2currency = {}
        for account_id, sum, currency_id in cursor.fetchall():
            account_sum.setdefault(account_id, Decimal('0.0'))
            if currency_id != id2account[account_id].currency.id:
                currency = None
                if currency_id in id2currency:
                    currency = id2currency[currency_id]
                else:
                    currency = currency_obj.browse(cursor, user, currency_id,
                            context=context)
                    id2currency[currency.id] = currency
                account_sum[account_id] += currency_obj.compute(cursor, user,
                        currency, sum, id2account[account_id].currency,
                        round=True, context=context)
            else:
                account_sum[account_id] += currency_obj.round(cursor, user,
                        id2account[account_id].currency, sum)

        for account_id in ids:
            res.setdefault(account_id, Decimal('0.0'))
            child_ids = self.search(cursor, user, [
                ('parent', 'child_of', [account_id]),
                ], context=context)
            to_currency = id2account[account_id].currency
            for child_id in child_ids:
                from_currency = id2account[child_id].currency
                res[account_id] += currency_obj.compute(cursor, user,
                        from_currency, account_sum.get(child_id, Decimal('0.0')),
                        to_currency, round=True, context=context)
            res[account_id] = currency_obj.round(cursor, user, to_currency,
                    res[account_id])
            if id2account[account_id].display_balance == 'credit-debit':
                res[account_id] = - res[account_id]
        return res

    def get_credit_debit(self, cursor, user, ids, name, arg, context=None):
        res = {}
        line_obj = self.pool.get('analytic_account.line')
        currency_obj = self.pool.get('currency.currency')

        if name not in ('credit', 'debit'):
            raise Exception('Bad argument')

        id2account = {}
        accounts = self.browse(cursor, user, ids, context=context)
        for account in accounts:
            res[account.id] = Decimal('0.0')
            id2account[account.id] = account

        line_query = line_obj.query_get(cursor, user, context=context)
        cursor.execute('SELECT a.id, ' \
                    'SUM(COALESCE(l.' + name + ', 0)), ' \
                    'l.currency ' \
                'FROM analytic_account_account a ' \
                    'LEFT JOIN analytic_account_line l ' \
                    'ON (a.id = l.account) ' \
                'WHERE a.type != \'view\' ' \
                    'AND a.id IN (' + \
                        ','.join(['%s' for x in ids]) + ') ' \
                    'AND ' + line_query + ' ' \
                    'AND a.active ' \
                'GROUP BY a.id, l.currency', ids)

        id2currency = {}
        for account_id, sum, currency_id in cursor.fetchall():
            if currency_id != id2account[account_id].currency.id:
                currency = None
                if currency_id in id2currency:
                    currency = id2currency[currency_id]
                else:
                    currency = currency_obj.browse(cursor, user, currency_id,
                            context=context)
                    id2currency[currency.id] = currency
                res[account_id] += currency_obj.compute(cursor, user,
                        currency, sum, id2account[account_id].currency,
                        round=True, context=context)
            else:
                res[account_id] += currency_obj.round(cursor, user,
                        id2account[account_id].currency, sum)
        return res

    def name_search(self, cursor, user, name='', args=None, operator='ilike',
            context=None, limit=None):
        if name:
            ids = self.search(cursor, user,
                    [('code', 'like', name + '%')] + args,
                    limit=limit, context=context)
            if not ids:
                ids = self.search(cursor, user,
                        [(self._rec_name, operator, name)] + args,
                        limit=limit, context=context)
        else:
            ids = self.search(cursor, user, args, limit=limit, context=context)
        res = self.name_get(cursor, user, ids, context=context)
        return res

    def name_get(self, cursor, user, ids, context=None):
        if not ids:
            return []
        if isinstance(ids, (int, long)):
            ids = [ids]
        return [(r['id'], r['code'] and r['code'] + ' - ' + unicode(r[self._rec_name]) \
                or unicode(r[self._rec_name])) for r in self.read(cursor, user, ids,
                    [self._rec_name, 'code'], context=context, load='_classic_write')]

    def convert_view(self, cursor, user, tree, context=None):
        res = tree.xpath('//field[@name=\'analytic_accounts\']')
        if not res:
            return
        element_accounts = res[0]

        root_account_ids = self.search(cursor, user, [
            ('parent', '=', False),
            ], context=context)
        if not root_account_ids:
            element_accounts.getparent().getparent().remove(
                    element_accounts.getparent())
            return
        for account_id in root_account_ids:
            newelement = copy.copy(element_accounts)
            newelement.tag = 'label'
            newelement.set('name', 'analytic_account_' + str(account_id))
            element_accounts.addprevious(newelement)
            newelement = copy.copy(element_accounts)
            newelement.set('name', 'analytic_account_' + str(account_id))
            element_accounts.addprevious(newelement)
        parent = element_accounts.getparent()
        parent.remove(element_accounts)

    def analytic_accounts_fields_get(self, cursor, user, field,
            fields_names=None, context=None):
        res = {}
        if fields_names is None:
            fields_names = []

        root_account_ids = self.search(cursor, user, [
            ('parent', '=', False),
            ], context=context)
        for account in self.browse(cursor, user, root_account_ids,
                context=context):
            name = 'analytic_account_' + str(account.id)
            if name in fields_names or not fields_names:
                res[name] = field.copy()
                res[name]['required'] = account.mandatory
                res[name]['string'] = account.name
                res[name]['relation'] = self._name
                res[name]['domain'] = [('root', '=', account.id),
                        ('type', '=', 'normal')]
        return res

Account()


class OpenChartAccountInit(WizardOSV):
    _name = 'analytic_account.account.open_chart_account.init'
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')

OpenChartAccountInit()


class OpenChartAccount(Wizard):
    'Open Chart Of Account'
    _name = 'analytic_account.account.open_chart_account'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'analytic_account.account.open_chart_account.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('open', 'Open', 'tryton-ok', True),
                ],
            },
        },
        'open': {
            'result': {
                'type': 'action',
                'action': '_action_open_chart',
                'state': 'end',
            },
        },
    }

    def _action_open_chart(self, cursor, user, data, context=None):
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')

        model_data_ids = model_data_obj.search(cursor, user, [
            ('fs_id', '=', 'act_account_tree2'),
            ('module', '=', 'analytic_account'),
            ], limit=1, context=context)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                context=context)
        res = act_window_obj.read(cursor, user, model_data.db_id, context=context)
        res['context'] = str({
            'start_date': data['form']['start_date'],
            'end_date': data['form']['end_date']
            })
        return res

OpenChartAccount()


class AccountSelection(OSV):
    'Analytic Account Selection'
    _name = 'analytic_account.account.selection'
    _description = __doc__
    _rec_name = 'id'

    accounts = fields.Many2Many('analytic_account.account',
            'analytic_account_account_selection_rel', 'selection', 'account',
            'Accounts')

    def __init__(self):
        super(AccountSelection, self).__init__()
        self._constraints += [
            ('check_root', 'Can not have many accounts with the same root ' \
                    'or a missing mandatory root account!',
                ['accounts']),
        ]

    def check_root(self, cursor, user, ids):
        "Check Root"
        account_obj = self.pool.get('analytic_account.account')

        root_account_ids = account_obj.search(cursor, user, [
            ('parent', '=', False),
            ])
        root_accounts = account_obj.browse(cursor, user, root_account_ids)

        selections = self.browse(cursor, user, ids)
        for selection in selections:
            roots = []
            for account in selection.accounts:
                if account.root.id in roots:
                    return False
                roots.append(account.root.id)
            for account in root_accounts:
                if account.mandatory:
                    if not account.id in roots:
                        return False
        return True

AccountSelection()
