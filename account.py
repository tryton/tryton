#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
"Account"

from trytond.osv import fields, OSV
from trytond.osv.orm import ID_MAX, exclude
from trytond.wizard import Wizard, WizardOSV
from trytond.report import Report
from decimal import Decimal
import datetime
import time
import locale
import os
from trytond.report.report import _LOCALE2WIN32
from _strptime import LocaleTime


class Type(OSV):
    'Account Type'
    _name = 'account.account.type'
    _description = __doc__
    name = fields.Char('Name', size=None, required=True, translate=True)
    parent = fields.Many2One('account.account.type', 'Parent')
    childs = fields.One2Many('account.account.type', 'parent', 'Childs')
    sequence = fields.Integer('Sequence', required=True,
            help='Use to order the account type')
    #TODO fix digits depend of the currency
    amount = fields.Function('get_amount', digits=(16, 2), string='Amount')
    balance_sheet = fields.Boolean('Balance Sheet', states={
        'invisible': "parent",
        })
    income_statement = fields.Boolean('Income Statement', states={
        'invisible': "parent",
        })
    display_balance = fields.Selection([
        ('debit-credit', 'Debit - Credit'),
        ('credit-debit', 'Credit - Debit'),
        ], 'Display Balance', required=True)

    def __init__(self):
        super(Type, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))

    def default_balance_sheet(self, cursor, user, context=None):
        return False

    def default_income_statement(self, cursor, user, context=None):
        return False

    def default_display_balance(self, cursor, user, context=None):
        return 'debit-credit'

    def get_amount(self, cursor, user, ids, name, arg, context=None):
        company_obj = self.pool.get('company.company')
        account_obj = self.pool.get('account.account')
        currency_obj = self.pool.get('currency.currency')

        if context is None:
            context = {}
        res = {}
        for type_id in ids:
            res[type_id] = Decimal('0.0')

        if not context.get('company'):
            return res
        company = company_obj.browse(cursor, user, context['company'],
                context=context)

        child_ids = self.search(cursor, user, [
            ('parent', 'child_of', ids),
            ], context=context)
        type_sum = {}
        for type_id in child_ids:
            type_sum[type_id] = Decimal('0.0')

        account_ids = account_obj.search(cursor, user, [
            ('type', 'in', child_ids),
            ('company', '=', company.id),
            ], context=context)
        for account in account_obj.browse(cursor, user, account_ids,
                context=context):
            type_sum[account.type.id] += currency_obj.round(cursor, user,
                    company.currency, account.debit - account.credit)

        types = self.browse(cursor, user, ids, context=context)
        for type in types:
            child_ids = self.search(cursor, user, [
                ('parent', 'child_of', [type.id]),
                ], context=context)
            for child_id in child_ids:
                res[type.id] += type_sum[child_id]
            res[type.id] = currency_obj.round(cursor, user,
                        company.currency, res[type.id])
            if type.display_balance == 'credit-debit':
                res[type.id] = - res[type.id]
        return res

    def name_get(self, cursor, user, ids, context=None):
        if not ids:
            return []
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = []
        def _name(type):
            if type.parent:
                return _name(type.parent) + '\\' + type.name
            else:
                return type.name
        for type in self.browse(cursor, user, ids, context=context):
            res.append((type.id, _name(type)))
        return res

Type()


class AccountTemplate(OSV):
    'Account Template'
    _name = 'account.account.template'
    _description = __doc__

    name = fields.Char('Name', size=None, required=True, translate=True,
            select=1)
    complete_name = fields.Function('get_complete_name', type='char',
            string='Name', order_field='code')
    code = fields.Char('Code', size=None, select=1)
    type = fields.Many2One('account.account.type', 'Type',
            states={
                'invisible': "kind == 'view'",
                'required': "kind != 'view'",
            })
    parent = fields.Many2One('account.account.template', 'Parent', select=1)
    childs = fields.One2Many('account.account.template', 'parent', 'Childs')
    reconcile = fields.Boolean('Reconcile',
            states={
                'invisible': "kind == 'view'",
            })
    close_method = fields.Selection([
        ('none', 'None'),
        ('balance', 'Balance'),
        ('detail', 'Detail'),
        ('unreconciled', 'Unreconciled'),
        ], 'Deferral method',
            states={
                'invisible': "kind == 'view'",
                'required': "kind != 'view'",
            })
    kind = fields.Selection([
        (None, ''),
        ('payable', 'Payable'),
        ('revenue', 'Revenue'),
        ('receivable', 'Receivable'),
        ('expense', 'Expense'),
        ('view', 'View'),
        ], 'Kind')

    def __init__(self):
        super(AccountTemplate, self).__init__()
        self._constraints += [
            ('check_recursion',
                'Error! You can not create recursive accounts.', ['parent']),
        ]
        self._order.insert(0, ('code', 'ASC'))
        self._order.insert(1, ('name', 'ASC'))

    def default_kind(self, cursor, user, context=None):
        return 'view'

    def get_complete_name(self, cursor, user, ids, name, arg, context=None):
        res = self.name_get(cursor, user, ids, context=context)
        return dict(res)

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
        return [(r['id'], r['code'] and r['code'] + ' - ' + str(r[self._rec_name]) \
                or str(r[self._rec_name])) for r in self.read(cursor, user, ids,
                    [self._rec_name, 'code'], context=context, load='_classic_write')]


    def _get_account_value(self, cursor, user, template, context=None):
        res = {}
        res['name'] = template.name
        res['code'] = template.code
        res['kind'] = template.kind
        res['type'] = template.type.id
        res['reconcile'] = template.reconcile
        res['close_method'] = template.close_method
        res['taxes'] = [('add', x.id) for x in template.taxes]
        return res

    def create_account(self, cursor, user, template, company_id, context=None,
            template2account=None, parent_id=False):
        account_obj = self.pool.get('account.account')

        if template2account is None:
            template2account = {}

        if isinstance(template, (int, long)):
            template = self.browse(cursor, user, template, context=context)

        if template.id not in template2account:
            vals = self._get_account_value(cursor, user, template, context=context)
            vals['company'] = company_id
            vals['parent'] = parent_id

            new_id = account_obj.create(cursor, user, vals, context=context)
            template2account[template.id] = new_id
        else:
            new_id = template2account[template.id]

        new_childs = []
        for child in template.childs:
            new_childs.append(self.create_account(cursor, user, child,
                company_id, context=context, template2account=template2account,
                parent_id=new_id))
        return new_id

AccountTemplate()


class Account(OSV):
    'Account'
    _name = 'account.account'
    _description = __doc__

    name = fields.Char('Name', size=None, required=True, translate=True,
            select=1)
    complete_name = fields.Function('get_complete_name', type='char',
            string='Name', order_field='code')
    code = fields.Char('Code', size=None, select=1)
    active = fields.Boolean('Active', select=2)
    company = fields.Many2One('company.company', 'Company', required=True)
    currency = fields.Function('get_currency', type='many2one',
            relation='currency.currency', string='Currency')
    second_currency = fields.Many2One('currency.currency', 'Secondary currency',
            help='Force all moves for this account \n' \
                    'to have this secondary currency.')
    type = fields.Many2One('account.account.type', 'Type',
            states={
                'invisible': "kind == 'view'",
                'required': "kind != 'view'",
            })
    parent = fields.Many2One('account.account', 'Parent', select=1,
            left="left", right="right")
    left = fields.Integer('Left', required=True)
    right = fields.Integer('Right', required=True)
    childs = fields.One2Many('account.account', 'parent', 'Childs')
    #TODO fix digits depend of the currency
    balance = fields.Function('get_balance', digits=(16, 2), string='Balance')
    credit = fields.Function('get_credit_debit', digits=(16, 2), string='Credit')
    debit = fields.Function('get_credit_debit', digits=(16, 2), string='Debit')
    reconcile = fields.Boolean('Reconcile',
            help='Check if the account can be used \n' \
                    'for reconciliation.',
            states={
                'invisible': "kind == 'view'",
            })
    close_method = fields.Selection([
        ('none', 'None'),
        ('balance', 'Balance'),
        ('detail', 'Detail'),
        ('unreconciled', 'Unreconciled'),
        ], 'Deferral method',
            help='How to process the lines of this account ' \
                    'when closing the fiscal year\n' \
                    '- None: to start with an empty account\n'
                    '- Balance: to create one entry to keep the balance\n'
                    '- Detail: to keep all entries\n'
                    '- Unreconciled: to keep all unreconciled entries',
            states={
                'invisible': "kind == 'view'",
                'required': "kind != 'view'",
            })
    note = fields.Text('Note')
    kind = fields.Selection([
        (None, ''),
        ('payable', 'Payable'),
        ('revenue', 'Revenue'),
        ('receivable', 'Receivable'),
        ('expense', 'Expense'),
        ('view', 'View'),
        ], 'Kind')

    def __init__(self):
        super(Account, self).__init__()
        self._constraints += [
            ('check_recursion',
                'Error! You can not create recursive accounts.', ['parent']),
        ]
        self._order.insert(0, ('code', 'ASC'))
        self._order.insert(1, ('name', 'ASC'))

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

    def default_reconcile(self, cursor, user, context=None):
        return False

    def default_close_method(self, cursor, user, context=None):
        return 'balance'

    def default_kind(self, cursor, user, context=None):
        return 'view'

    def default_code(self, cursor, user, context=None):
        return 'view'

    def get_complete_name(self, cursor, user, ids, name, arg, context=None):
        res = self.name_get(cursor, user, ids, context=context)
        return dict(res)

    def get_currency(self, cursor, user, ids, name, arg, context=None):
        currency_obj = self.pool.get('currency.currency')
        res = {}
        for account in self.browse(cursor,user, ids, context=context):
            res[account.id] = account.company.currency.id
        currency_names = {}
        for currency_id, currency_name in currency_obj.name_get(cursor, user,
                [x for x in res.values() if x], context=context):
            currency_names[currency_id] = currency_name

        for i in res.keys():
            if res[i] and res[i] in currency_names:
                res[i] = (res[i], currency_names[res[i]])
            else:
                res[i] = False
        return res

    def get_balance(self, cursor, user, ids, name, arg, context=None):
        res = {}
        company_obj = self.pool.get('company.company')
        currency_obj = self.pool.get('currency.currency')
        move_line_obj = self.pool.get('account.move.line')

        query_ids, args_ids = self.search(cursor, user, [
            ('parent', 'child_of', ids),
            ], context=context, query_string=True)
        line_query = move_line_obj.query_get(cursor, user, context=context)
        cursor.execute('SELECT a.id, ' \
                    'SUM((COALESCE(l.debit, 0) - COALESCE(l.credit, 0))) ' \
                'FROM account_account a ' \
                    'LEFT JOIN account_move_line l ' \
                    'ON (a.id = l.account) ' \
                    'JOIN account_account_type t ' \
                    'ON (a.type = t.id) ' \
                'WHERE t.code != \'view\' ' \
                    'AND a.id IN (' + query_ids + ') ' \
                    'AND ' + line_query + ' ' \
                    'AND a.active ' \
                'GROUP BY a.id', args_ids)
        account_sum = {}
        for account_id, sum in cursor.fetchall():
            account_sum[account_id] = sum

        account2company = {}
        id2company = {}
        id2account = {}
        all_ids = self.search(cursor, user, [('parent', 'child_of', ids)],
                context=context)
        accounts = self.browse(cursor, user, all_ids, context=context)
        for account in accounts:
            account2company[account.id] = account.company.id
            id2company[account.company.id] = account.company
            id2account[account.id] = account

        for account_id in ids:
            res.setdefault(account_id, Decimal('0.0'))
            child_ids = self.search(cursor, user, [
                ('parent', 'child_of', [account_id]),
                ], context=context)
            company_id = account2company[account_id]
            to_currency = id2company[company_id].currency
            for child_id in child_ids:
                child_company_id = account2company[child_id]
                from_currency = id2company[child_company_id].currency
                res[account_id] += currency_obj.compute(cursor, user,
                        from_currency, account_sum.get(child_id, Decimal('0.0')),
                        to_currency, round=True, context=context)
            res[account_id] = currency_obj.round(cursor, user, to_currency,
                    res[account_id])
        return res

    def get_credit_debit(self, cursor, user, ids, name, arg, context=None):
        res = {}
        move_line_obj = self.pool.get('account.move.line')
        company_obj = self.pool.get('company.company')
        currency_obj = self.pool.get('currency.currency')

        if name not in ('credit', 'debit'):
            raise Exception('Bad argument')

        line_query = move_line_obj.query_get(cursor, user, context=context)
        cursor.execute('SELECT a.id, ' \
                    'SUM(COALESCE(l.' + name + ', 0)) ' \
                'FROM account_account a ' \
                    'LEFT JOIN account_move_line l ' \
                    'ON (a.id = l.account) ' \
                'WHERE a.code != \'view\' ' \
                    'AND a.id IN (' + \
                        ','.join(['%s' for x in ids]) + ') ' \
                    'AND ' + line_query + ' ' \
                    'AND a.active ' \
                'GROUP BY a.id', ids)
        for account_id, sum in cursor.fetchall():
            res[account_id] = sum

        account2company = {}
        id2company = {}
        accounts = self.browse(cursor, user, ids, context=context)
        for account in accounts:
            account2company[account.id] = account.company.id
            id2company[account.company.id] = account.company

        for account_id in ids:
            res.setdefault(account_id, Decimal('0.0'))
            company_id = account2company[account_id]
            currency = id2company[company_id].currency
            res[account_id] = currency_obj.round(cursor, user, currency,
                    res[account_id])
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
        return [(r['id'], r['code'] and r['code'] + ' - ' + str(r[self._rec_name]) \
                or str(r[self._rec_name])) for r in self.read(cursor, user, ids,
                    [self._rec_name, 'code'], context=context, load='_classic_write')]

    def copy(self, cursor, user, object_id, default=None, context=None):
        account = self.browse(cursor, user, object_id, context=context)
        default['parent'] = False
        if account:
            #Also duplicate all childs
            new_child_ids = []
            for child in account.childs:
                new_child_ids.append(
                        self.copy(cursor, user, child.id, default,
                            context=context))
            default['childs'] = [('set', new_child_ids)]
        else:
            default['childs'] = False
        return super(Account, self).copy(cursor, user, object_id, default,
                context=context)

    def write(self, cursor, user, ids, vals, context=None):
        if not vals.get('active', True):
            move_line_obj = self.pool.get('account.move.line')
            account_ids = self.search(cursor, user, [
                ('parent', 'child_of', ids),
                ], context=context)
            if move_line_obj.search(cursor, user, [
                ('account', 'in', account_ids),
                ], context=context):
                vals = vals.copy()
                del vals['active']
        return super(Account, self).write(cursor, user, ids, vals,
                context=context)

Account()


class OpenChartAccountInit(WizardOSV):
    _name = 'account.account.open_chart_account.init'
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
            help='Keep empty for all open fiscal year')
    posted = fields.Boolean('Posted Move', help='Only posted move')

    def default_posted(self, cursor, user, context=None):
        return False

OpenChartAccountInit()


class OpenChartAccount(Wizard):
    'Open Chart Of Account'
    _name = 'account.account.open_chart_account'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'account.account.open_chart_account.init',
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
            ('module', '=', 'account'),
            ], limit=1, context=context)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                context=context)
        res = act_window_obj.read(cursor, user, model_data.db_id, context=context)
        res['context'] = str({
            'fiscalyear': data['form']['fiscalyear'],
            'posted': data['form']['posted'],
            })
        return res

OpenChartAccount()


class Party(OSV):
    _name = 'relationship.party'
    account_payable = fields.Property(type='many2one',
            relation='account.account', string='Account Payable',
            group_name='Accounting Properties', view_load=True,
            domain="[('kind', '=', 'payable'), ('company', '=', company)]",
            states={
                'required': "company",
                'invisible': "not company",
            })
    account_receivable = fields.Property(type='many2one',
            relation='account.account', string='Account Receivable',
            group_name='Accounting Properties', view_load=True,
            domain="[('kind', '=', 'receivable'), ('company', '=', company)]",
            states={
                'required': "company",
                'invisible': "not company",
            })

Party()


class PrintGeneralLegderInit(WizardOSV):
    _name = 'account.account.print_general_ledger.init'
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
            required=True, on_change=['fiscalyear'])
    start_period = fields.Many2One('account.period', 'Start Period',
            domain="[('fiscalyear', '=', fiscalyear), " \
                    "('start_date', '<=', (end_period, 'start_date'))]")
    end_period = fields.Many2One('account.period', 'End Period',
            domain="[('fiscalyear', '=', fiscalyear), " \
                    "('start_date', '>=', (start_period, 'start_date'))]")
    company = fields.Many2One('company.company', 'Company', required=True)
    posted = fields.Boolean('Posted Move', help='Only posted move')

    def default_fiscalyear(self, cursor, user, context=None):
        fiscalyear_obj = self.pool.get('account.fiscalyear')
        if context is None:
            context = {}
        fiscalyear_id = fiscalyear_obj.find(cursor, user,
                context.get('company', False), exception=False, context=context)
        if fiscalyear_id:
            return fiscalyear_obj.name_get(cursor, user, fiscalyear_id,
                    context=context)[0]
        return False

    def default_company(self, cursor, user, context=None):
        if context is None:
            context = {}
        company_obj = self.pool.get('company.company')
        if context.get('company'):
            return company_obj.name_get(cursor, user, context['company'],
                    context=context)[0]
        return False

    def default_posted(self, cursor, user, context=None):
        return False

    def on_change_fiscalyear(self, cursor, user, ids, vals, context=None):
        return {
            'start_period': False,
            'end_period': False,
        }

PrintGeneralLegderInit()


class PrintGeneralLegder(Wizard):
    'Print General Legder'
    _name = 'account.account.print_general_ledger'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'account.account.print_general_ledger.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('print', 'Print', 'tryton-print', True),
                ],
            },
        },
        'print': {
            'result': {
                'type': 'print',
                'report': 'account.account.general_ledger',
                'state': 'end',
            },
        },
    }

PrintGeneralLegder()


class GeneralLegder(Report):
    _name = 'account.account.general_ledger'

    def _get_objects(self, cursor, user, ids, model, datas, context):
        #Don't browse false account
        return None

    def parse(self, cursor, user, report, objects, datas, context):
        if context is None:
            context = {}
        context = context.copy()
        account_obj = self.pool.get('account.account')
        period_obj = self.pool.get('account.period')
        company_obj = self.pool.get('company.company')

        company = company_obj.browse(cursor, user,
                datas['form']['company'], context=context)

        account_ids = account_obj.search(cursor, user, [
            ('company', '=', datas['form']['company']),
            ], order=[('code', 'ASC'), ('id', 'ASC')], context=context)

        start_period_ids = [0]
        if datas['form']['start_period']:
            start_period = period_obj.browse(cursor, user,
                    datas['form']['start_period'], context=context)
            start_period_ids = period_obj.search(cursor, user, [
                ('fiscalyear', '=', datas['form']['fiscalyear']),
                ('end_date', '<=', start_period.start_date),
                ], context=context)

        start_context = context.copy()
        start_context['fiscalyear'] = datas['form']['fiscalyear']
        start_context['periods'] = start_period_ids
        start_context['posted'] = datas['form']['posted']
        start_accounts = account_obj.browse(cursor, user, account_ids,
                context=start_context)
        id2start_account = {}
        for account in start_accounts:
            id2start_account[account.id] = account

        end_period_ids = []
        if datas['form']['end_period']:
            end_period = period_obj.browse(cursor, user,
                    datas['form']['end_period'], context=context)
            end_period_ids = period_obj.search(cursor, user, [
                ('fiscalyear', '=', datas['form']['fiscalyear']),
                ('end_date', '<=', end_period.start_date),
                ], context=context)
            end_period_ids = exclude(end_period_ids, start_period_ids)
            if datas['form']['end_period'] not in end_period_ids:
                end_period_ids.append(datas['form']['end_period'])
        else:
            end_period_ids = period_obj.search(cursor, user, [
                ('fiscalyear', '=', datas['form']['fiscalyear']),
                ], context=context)
            end_period_ids = exclude(end_period_ids, start_period_ids)

        end_context = context.copy()
        end_context['fiscalyear'] = datas['form']['fiscalyear']
        end_context['periods'] = end_period_ids
        end_context['posted'] = datas['form']['posted']
        end_accounts = account_obj.browse(cursor, user, account_ids,
                context=end_context)
        id2end_account = {}
        for account in end_accounts:
            id2end_account[account.id] = account

        periods = period_obj.browse(cursor, user, end_period_ids,
                context=context)
        periods.sort(lambda x, y: cmp(x.start_date, y.start_date))
        context['start_period'] = periods[0]
        periods.sort(lambda x, y: cmp(x.end_date, y.end_date))
        context['end_period'] = periods[-1]

        context['accounts'] = account_obj.browse(cursor, user, account_ids,
                context=context)
        context['id2start_account'] = id2start_account
        context['id2end_account'] = id2end_account
        context['digits'] = company.currency.digits
        context['lines'] = lambda account_id: self.lines(cursor, user,
                account_id, end_period_ids, datas['form']['posted'], context)
        context['company'] = company

        return super(GeneralLegder, self).parse(cursor, user, report, objects,
                datas, context)

    def lines(self, cursor, user, account_id, period_ids, posted, context):
        move_line_obj = self.pool.get('account.move.line')
        period_obj = self.pool.get('account.period')
        res = []

        clause = [
            ('account', '=', account_id),
            ('period', 'in', period_ids),
            ('state', '!=', 'draft'),
            ]
        if posted:
            clause.append(('move.state', '=', 'posted'))
        move_line_ids = move_line_obj.search(cursor, user, clause,
                context=context)
        move_lines = move_line_obj.browse(cursor, user, move_line_ids,
                context=context)
        move_lines.sort(lambda x, y: cmp(x.date, y.date))

        balance = Decimal('0.0')
        for line in move_lines:
            balance += line.debit - line.credit
            res.append({
                'date': line.date,
                'debit': line.debit,
                'credit': line.credit,
                'balance': balance,
                'name': line.name,
                'state': line.move.state,
                })
        return res

GeneralLegder()


class PrintTrialBalanceInit(WizardOSV):
    _name = 'account.account.print_trial_balance.init'
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
            required=True, on_change=['fiscalyear'])
    start_period = fields.Many2One('account.period', 'Start Period',
            domain="[('fiscalyear', '=', fiscalyear), " \
                    "('start_date', '<=', (end_period, 'start_date'))]")
    end_period = fields.Many2One('account.period', 'End Period',
            domain="[('fiscalyear', '=', fiscalyear), " \
                    "('start_date', '>=', (start_period, 'start_date'))]")
    company = fields.Many2One('company.company', 'Company', required=True)
    posted = fields.Boolean('Posted Move', help='Only posted move')

    def default_fiscalyear(self, cursor, user, context=None):
        fiscalyear_obj = self.pool.get('account.fiscalyear')
        if context is None:
            context = {}
        fiscalyear_id = fiscalyear_obj.find(cursor, user,
                context.get('company', False), exception=False, context=context)
        if fiscalyear_id:
            return fiscalyear_obj.name_get(cursor, user, fiscalyear_id,
                    context=context)[0]
        return False

    def default_company(self, cursor, user, context=None):
        if context is None:
            context = {}
        company_obj = self.pool.get('company.company')
        if context.get('company'):
            return company_obj.name_get(cursor, user, context['company'],
                    context=context)[0]
        return False

    def default_posted(self, cursor, user, context=None):
        return False

    def on_change_fiscalyear(self, cursor, user, ids, vals, context=None):
        return {
            'start_period': False,
            'end_period': False,
        }

PrintTrialBalanceInit()


class PrintTrialBalance(Wizard):
    'Print Trial Balance'
    _name = 'account.account.print_trial_balance'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'account.account.print_trial_balance.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('print', 'Print', 'tryton-print', True),
                ],
            },
        },
        'print': {
            'result': {
                'type': 'print',
                'report': 'account.account.trial_balance',
                'state': 'end',
            },
        },
    }

PrintTrialBalance()


class TrialBalance(Report):
    _name = 'account.account.trial_balance'

    def _get_objects(self, cursor, user, ids, model, datas, context):
        return None

    def parse(self, cursor, user, report, objects, datas, context):
        if context is None:
            context = {}
        context = context.copy()
        account_obj = self.pool.get('account.account')
        period_obj = self.pool.get('account.period')
        company_obj = self.pool.get('company.company')

        company = company_obj.browse(cursor, user,
                datas['form']['company'], context=context)

        account_ids = account_obj.search(cursor, user, [
            ('kind', '!=', 'view'),
            ], context=context)

        start_period_ids = [0]
        if datas['form']['start_period']:
            start_period = period_obj.browse(cursor, user,
                    datas['form']['start_period'], context=context)
            start_period_ids = period_obj.search(cursor, user, [
                ('fiscalyear', '=', datas['form']['fiscalyear']),
                ('end_date', '<=', start_period.start_date),
                ], context=context)

        end_period_ids = []
        if datas['form']['end_period']:
            end_period = period_obj.browse(cursor, user,
                    datas['form']['end_period'], context=context)
            end_period_ids = period_obj.search(cursor, user, [
                ('fiscalyear', '=', datas['form']['fiscalyear']),
                ('end_date', '<=', end_period.start_date),
                ], context=context)
            end_period_ids = exclude(end_period_ids, start_period_ids)
            if datas['form']['end_period'] not in end_period_ids:
                end_period_ids.append(datas['form']['end_period'])
        else:
            end_period_ids = period_obj.search(cursor, user, [
                ('fiscalyear', '=', datas['form']['fiscalyear']),
                ], context=context)
            end_period_ids = exclude(end_period_ids, start_period_ids)

        ctx = context.copy()
        ctx['fiscalyear'] = datas['form']['fiscalyear']
        ctx['periods'] = end_period_ids
        ctx['posted'] = datas['form']['posted']
        accounts = account_obj.browse(cursor, user, account_ids,
                context=ctx)

        periods = period_obj.browse(cursor, user, end_period_ids,
                context=context)

        context['accounts'] = accounts
        context['start_period'] = periods[0]
        context['end_period'] = periods[-1]
        context['company'] = company
        context['digits'] = company.currency.digits
        context['sum'] = lambda accounts, field: self.sum(cursor, user,
                accounts, field, context)

        return super(TrialBalance, self).parse(cursor, user, report, objects,
                datas, context)

    def sum(self, cursor, user, accounts, field, context):
        amount = Decimal('0.0')
        for account in accounts:
            amount += account[field]
        return amount

TrialBalance()


class OpenBalanceSheetInit(WizardOSV):
    _name = 'account.account.open_balance_sheet.init'
    date = fields.Date('Date', required=True)
    company = fields.Many2One('company.company', 'Company', required=True)
    posted = fields.Boolean('Posted Move', help='Only posted move')

    def default_date(self, cursor, user, context=None):
        return datetime.date.today()

    def default_company(self, cursor, user, context=None):
        if context is None:
            context = {}
        company_obj = self.pool.get('company.company')
        if context.get('company'):
            return company_obj.name_get(cursor, user, context['company'],
                    context=context)[0]
        return False

    def default_posted(self, cursor, user, context=None):
        return False

OpenBalanceSheetInit()


class OpenBalanceSheet(Wizard):
    'Open Balance Sheet'
    _name = 'account.account.open_balance_sheet'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'account.account.open_balance_sheet.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('open', 'Open', 'tryton-ok', True),
                ],
            },
        },
        'open': {
            'result': {
                'type': 'action',
                'action': '_action_open',
                'state': 'end',
            },
        },
    }

    def _action_open(self, cursor, user, datas, context=None):
        if context is None:
            context = {}
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')
        company_obj = self.pool.get('company.company')

        company = company_obj.browse(cursor, user, datas['form']['company'],
                context=context)
        lang = context.get('language', False) or 'en_US'
        try:
            if os.name == 'nt':
                locale.setlocale(locale.LC_ALL,
                        _LOCALE2WIN32.get(lang, lang) + '.' + encoding)
            else:
                locale.setlocale(locale.LC_ALL, lang + '.' + encoding)
        except:
            pass
        date = time.strptime(str(datas['form']['date']), '%Y-%m-%d')
        date = time.strftime(LocaleTime().LC_date.replace('%y', '%Y'), date)

        model_data_ids = model_data_obj.search(cursor, user, [
            ('fs_id', '=', 'act_account_balance_sheet_tree'),
            ('module', '=', 'account'),
            ], limit=1, context=context)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                context=context)
        res = act_window_obj.read(cursor, user, model_data.db_id, context=context)
        res['context'] = str({
            'date': datas['form']['date'],
            'posted': datas['form']['posted'],
            'company': datas['form']['company'],
            })
        res['name'] = res['name'] + ' - '+ date + ' - ' + company.name
        return res

OpenBalanceSheet()


class OpenIncomeStatementInit(WizardOSV):
    _name = 'account.account.open_income_statement.init'
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
            required=True, on_change=['fiscalyear'])
    start_period = fields.Many2One('account.period', 'Start Period',
            domain="[('fiscalyear', '=', fiscalyear), " \
                    "('start_date', '<=', (end_period, 'start_date'))]")
    end_period = fields.Many2One('account.period', 'End Period',
            domain="[('fiscalyear', '=', fiscalyear), " \
                    "('start_date', '>=', (start_period, 'start_date'))]")
    company = fields.Many2One('company.company', 'Company', required=True)
    posted = fields.Boolean('Posted Move', help='Only posted move')

    def default_fiscalyear(self, cursor, user, context=None):
        fiscalyear_obj = self.pool.get('account.fiscalyear')
        if context is None:
            context = {}
        fiscalyear_id = fiscalyear_obj.find(cursor, user,
                context.get('company', False), exception=False, context=context)
        if fiscalyear_id:
            return fiscalyear_obj.name_get(cursor, user, fiscalyear_id,
                    context=context)[0]
        return False

    def default_company(self, cursor, user, context=None):
        if context is None:
            context = {}
        company_obj = self.pool.get('company.company')
        if context.get('company'):
            return company_obj.name_get(cursor, user, context['company'],
                    context=context)[0]
        return False

    def default_posted(self, cursor, user, context=None):
        return False

    def on_change_fiscalyear(self, cursor, user, ids, vals, context=None):
        return {
            'start_period': False,
            'end_period': False,
        }

OpenIncomeStatementInit()


class OpenIncomeStatement(Wizard):
    'Open Income Statement'
    _name = 'account.account.open_income_statement'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'account.account.open_income_statement.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('open', 'Open', 'tryton-ok', True),
                ],
            },
        },
        'open': {
            'result': {
                'type': 'action',
                'action': '_action_open',
                'state': 'end',
            },
        },
    }

    def _action_open(self, cursor, user, datas, context=None):
        if context is None:
            context = {}
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')
        period_obj = self.pool.get('account.period')

        start_period_ids = [0]
        if datas['form']['start_period']:
            start_period = period_obj.browse(cursor, user,
                    datas['form']['start_period'], context=context)
            start_period_ids = period_obj.search(cursor, user, [
                ('fiscalyear', '=', datas['form']['fiscalyear']),
                ('end_date', '<=', start_period.start_date),
                ], context=context)

        end_period_ids = []
        if datas['form']['end_period']:
            end_period = period_obj.browse(cursor, user,
                    datas['form']['end_period'], context=context)
            end_period_ids = period_obj.search(cursor, user, [
                ('fiscalyear', '=', datas['form']['fiscalyear']),
                ('end_date', '<=', end_period.start_date),
                ], context=context)
            end_period_ids = exclude(end_period_ids, start_period_ids)
            if datas['form']['end_period'] not in end_period_ids:
                end_period_ids.append(datas['form']['end_period'])
        else:
            end_period_ids = period_obj.search(cursor, user, [
                ('fiscalyear', '=', datas['form']['fiscalyear']),
                ], context=context)
            end_period_ids = exclude(end_period_ids, start_period_ids)

        model_data_ids = model_data_obj.search(cursor, user, [
            ('fs_id', '=', 'act_account_income_statement_tree'),
            ('module', '=', 'account'),
            ], limit=1, context=context)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                context=context)
        res = act_window_obj.read(cursor, user, model_data.db_id, context=context)
        res['context'] = str({
            'periods': end_period_ids,
            'posted': datas['form']['posted'],
            'company': datas['form']['company'],
            })
        return res

OpenIncomeStatement()


class CreateChartAccountInit(WizardOSV):
    _name = 'account.account.create_chart_account.init'

CreateChartAccountInit()


class CreateChartAccountAccount(WizardOSV):
    _name = 'account.account.create_chart_account.account'
    company = fields.Many2One('company.company', 'Company', required=True)
    account_template = fields.Many2One('account.account.template',
            'Account Template', required=True, domain=[('parent', '=', False)])

CreateChartAccountAccount()


class CreateChartAccountPropertites(WizardOSV):
    _name = 'account.account.create_chart_account.properties'
    company = fields.Many2One('company.company', 'Company')
    account_receivable = fields.Many2One('account.account',
            'Default Receivable Account',
            domain="[('kind', '=', 'receivable'), ('company', '=', company)]")
    account_payable = fields.Many2One('account.account',
            'Default Payable Account',
            domain="[('kind', '=', 'payable'), ('company', '=', company)]")

CreateChartAccountPropertites()


class CreateChartAccount(Wizard):
    'Create chart account from template'
    _name = 'account.account.create_chart_account'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'account.account.create_chart_account.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('account', 'Ok', 'tryton-ok', True),
                ],
            },
        },
        'account': {
            'result': {
                'type': 'form',
                'object': 'account.account.create_chart_account.account',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('create_account', 'Create', 'tryton-ok', True),
                ],
            },
        },
        'create_account': {
            'actions': ['_action_create_account'],
            'result': {
                'type': 'form',
                'object': 'account.account.create_chart_account.properties',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('create_properties', 'Create', 'tryton-ok', True),
                ],
            },
        },
        'create_properties': {
            'result': {
                'type': 'action',
                'action': '_action_create_properties',
                'state': 'end',
            },
        },
    }

    def _action_create_account(self, cursor, user, datas, context=None):
        account_template_obj = self.pool.get('account.account.template')
        account_template_obj.create_account(cursor, user,
                datas['form']['account_template'], datas['form']['company'],
                context=context)
        return {'company': datas['form']['company']}

    def _action_create_properties(self, cursor, user, datas, context=None):
        property_obj = self.pool.get('ir.property')
        model_field_obj = self.pool.get('ir.model.field')

        account_receivable_field_id = model_field_obj.search(cursor, user, [
            ('model.model', '=', 'relationship.party'),
            ('name', '=', 'account_receivable'),
            ], limit=1, context=context)[0]
        property_ids = property_obj.search(cursor, user, [
            ('field', '=', account_receivable_field_id),
            ('res', '=', False),
            ('company', '=', datas['form']['company']),
            ], context=context)
        property_obj.unlink(cursor, user, property_ids, context=context)
        property_obj.create(cursor, user, {
            'name': 'account_receivable',
            'field': account_receivable_field_id,
            'value': 'account.account,' + \
                    str(datas['form']['account_receivable']),
            'company': datas['form']['company'],
            }, context=context)

        account_payable_field_id = model_field_obj.search(cursor, user, [
            ('model.model', '=', 'relationship.party'),
            ('name', '=', 'account_payable'),
            ], limit=1, context=context)[0]
        property_ids = property_obj.search(cursor, user, [
            ('field', '=', account_payable_field_id),
            ('res', '=', False),
            ('company', '=', datas['form']['company']),
            ], context=context)
        property_obj.unlink(cursor, user, property_ids, context=context)
        property_obj.create(cursor, user, {
            'name': 'account_payable',
            'field': account_payable_field_id,
            'value': 'account.account,' + \
                    str(datas['form']['account_payable']),
            'company': datas['form']['company'],
            }, context=context)
        return {}

CreateChartAccount()


class OpenThirdPartyBalanceInit(WizardOSV):
    _name = 'account.account.open_third_party_balance.init'
    company = fields.Many2One('company.company', 'Company', required=True)
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
            required=True)
    posted = fields.Boolean('Posted Move', help='Only posted move')


    def default_fiscalyear(self, cursor, user, context=None):
        fiscalyear_obj = self.pool.get('account.fiscalyear')
        if context is None:
            context = {}
        fiscalyear_id = fiscalyear_obj.find(cursor, user,
                context.get('company', False), exception=False, context=context)
        if fiscalyear_id:
            return fiscalyear_obj.name_get(cursor, user, fiscalyear_id,
                    context=context)[0]
        return False

    def default_posted(self, cursor, user, context=None):
        return False

    def default_company(self, cursor, user, context=None):
        if context is None:
            context = {}
        company_obj = self.pool.get('company.company')
        if context.get('company'):
            return company_obj.name_get(cursor, user, context['company'],
                    context=context)[0]
        return False

OpenThirdPartyBalanceInit()


class OpenThirdPartyBalance(Wizard):
    'Open Third Party Balance'
    _name = 'account.account.open_third_party_balance'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'account.account.open_third_party_balance.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('print', 'Print', 'tryton-ok', True),
                ],
            },
        },
        'print': {
            'result': {
                'type': 'print',
                'report': 'account.account.third_party_balance',
                'state': 'end',
            },
        },
    }

OpenThirdPartyBalance()


class ThirdPartyBalance(Report):
    _name = 'account.account.third_party_balance'

    def _get_objects(self, cursor, user, ids, model, datas, context):
        party_obj = self.pool.get('relationship.party')
        move_line_obj = self.pool.get('account.move.line')
        company_obj = self.pool.get('company.company')
        company = company_obj.browse(cursor, user,
                datas['form']['company'], context=context)
        context['company'] = company
        context['digits'] = company.currency.digits
        context['fiscalyear'] = datas['form']['fiscalyear']
        line_query = move_line_obj.query_get(cursor, user, context=context)
        if datas['form']['posted']:
            posted_clause = "and m.state = 'posted' "
        else:
            posted_clause = ""

        cursor.execute('SELECT l.party, SUM(l.debit), SUM(l.credit) ' \
                       'FROM account_move_line l ' \
                         'JOIN account_move m on (l.move = m.id) '
                         'JOIN account_account a on (l.account = a.id) '
                       'WHERE l.party is not null '\
                         'AND a.active ' \
                         'AND a.kind in (\'payable\',\'receivable\') ' \
                         'AND l.reconciliation IS NULL ' \
                         'AND a.company = %s ' \
                         'AND (l.maturity_date <= %s ' \
                               'OR l.maturity_date IS NULL) '\
                         'AND ' + line_query + ' ' \
                         + posted_clause + \
                       'GROUP BY l.party',
                       (datas['form']['company'],datetime.date.today()))

        res = cursor.fetchall()
        party_name = dict(party_obj.name_get(
                cursor, user, [x[0] for x in res],
                context=context))
        objects = [{'name': party_name[x[0]],
                 'debit': x[1],
                 'credit': x[2],
                 'solde': x[1]-x[2]} for x in res]
        objects.sort(lambda x,y: cmp(x['name'],y['name']))
        context['total_debit'] = sum((o['debit'] for o in objects))
        context['total_credit'] = sum((o['credit'] for o in objects))
        context['total_solde'] = sum((o['solde'] for o in objects))
        return objects

ThirdPartyBalance()
