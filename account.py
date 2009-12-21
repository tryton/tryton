#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Account"

from trytond.osv import fields, OSV
from trytond.osv.orm import exclude
from trytond.wizard import Wizard, WizardOSV
from trytond.report import Report
from decimal import Decimal
import datetime
import time
import os
import mx.DateTime


class TypeTemplate(OSV):
    'Account Type Template'
    _name = 'account.account.type.template'
    _description = __doc__
    name = fields.Char('Name', required=True, translate=True)
    parent = fields.Many2One('account.account.type.template', 'Parent',
            ondelete="restrict")
    childs = fields.One2Many('account.account.type.template', 'parent', 'Childs')
    sequence = fields.Integer('Sequence', required=True)
    balance_sheet = fields.Boolean('Balance Sheet')
    income_statement = fields.Boolean('Income Statement')
    display_balance = fields.Selection([
        ('debit-credit', 'Debit - Credit'),
        ('credit-debit', 'Credit - Debit'),
        ], 'Display Balance', required=True)

    def __init__(self):
        super(TypeTemplate, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))

    def default_balance_sheet(self, cursor, user, context=None):
        return False

    def default_income_statement(self, cursor, user, context=None):
        return False

    def default_display_balance(self, cursor, user, context=None):
        return 'debit-credit'

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

    def _get_type_value(self, cursor, user, template, context=None):
        '''
        Set the values for account creation.

        :param cursor: the database cursor
        :param user: the user id
        :param template: the BrowseRecord of the template
        :param context: the context
        :return: a dictionary with account fields as key and values as value
        '''
        res = {}
        res['name'] = template.name
        res['sequence'] = template.sequence
        res['balance_sheet'] = template.balance_sheet
        res['income_statement'] = template.income_statement
        res['display_balance'] = template.display_balance
        return res

    def create_type(self, cursor, user, template, company_id, context=None,
            template2type=None, parent_id=False):
        '''
        Create recursively types based on template.

        :param cursor: the database cursor
        :param user: the user id
        :param template: the template id or the BrowseRecord of the template
                used for type creation
        :param company_id: the id of the company for which types are created
        :param context: the context
        :param template2type: a dictionary with template id as key
                and type id as value, used to convert template id
                into type. The dictionary is filled with new types
        :param parent_id: the type id of the parent of the types that must
                be created
        :return: id of the type created
        '''
        type_obj = self.pool.get('account.account.type')

        if template2type is None:
            template2type = {}

        if isinstance(template, (int, long)):
            template = self.browse(cursor, user, template, context=context)

        if template.id not in template2type:
            vals = self._get_type_value(cursor, user, template, context=context)
            vals['company'] = company_id
            vals['parent'] = parent_id

            new_id = type_obj.create(cursor, user, vals, context=context)
            template2type[template.id] = new_id
        else:
            new_id = template2type[template.id]

        new_childs = []
        for child in template.childs:
            new_childs.append(self.create_type(cursor, user, child, company_id,
                context=context, template2type=template2type, parent_id=new_id))
        return new_id

TypeTemplate()


class Type(OSV):
    'Account Type'
    _name = 'account.account.type'
    _description = __doc__
    name = fields.Char('Name', size=None, required=True, translate=True)
    parent = fields.Many2One('account.account.type', 'Parent',
            ondelete="restrict")
    childs = fields.One2Many('account.account.type', 'parent', 'Childs')
    sequence = fields.Integer('Sequence', required=True,
            help='Use to order the account type')
    currency_digits = fields.Function('get_currency_digits', type='integer',
            string='Currency Digits')
    amount = fields.Function('get_amount', digits="(16, currency_digits)",
            string='Amount')
    balance_sheet = fields.Boolean('Balance Sheet')
    income_statement = fields.Boolean('Income Statement')
    display_balance = fields.Selection([
        ('debit-credit', 'Debit - Credit'),
        ('credit-debit', 'Credit - Debit'),
        ], 'Display Balance', required=True)
    company = fields.Many2One('company.company', 'Company', required=True,
            ondelete="restrict")

    def __init__(self):
        super(Type, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))

    def default_balance_sheet(self, cursor, user, context=None):
        return False

    def default_income_statement(self, cursor, user, context=None):
        return False

    def default_display_balance(self, cursor, user, context=None):
        return 'debit-credit'

    def get_currency_digits(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for type in self.browse(cursor, user, ids, context=context):
            res[type.id] = type.company.currency.digits
        return res

    def get_amount(self, cursor, user, ids, name, arg, context=None):
        account_obj = self.pool.get('account.account')
        currency_obj = self.pool.get('currency.currency')

        if context is None:
            context = {}
        res = {}
        for type_id in ids:
            res[type_id] = Decimal('0.0')

        child_ids = self.search(cursor, user, [
            ('parent', 'child_of', ids),
            ], context=context)
        type_sum = {}
        for type_id in child_ids:
            type_sum[type_id] = Decimal('0.0')

        account_ids = account_obj.search(cursor, user, [
            ('type', 'in', child_ids),
            ], context=context)
        for account in account_obj.browse(cursor, user, account_ids,
                context=context):
            type_sum[account.type.id] += currency_obj.round(cursor, user,
                    account.company.currency, account.debit - account.credit)

        types = self.browse(cursor, user, ids, context=context)
        for type in types:
            child_ids = self.search(cursor, user, [
                ('parent', 'child_of', [type.id]),
                ], context=context)
            for child_id in child_ids:
                res[type.id] += type_sum[child_id]
            res[type.id] = currency_obj.round(cursor, user,
                        type.company.currency, res[type.id])
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

    def delete(self, cursor, user, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        type_ids = self.search(cursor, user, [
            ('parent', 'child_of', ids),
            ], context=context)
        return super(Type, self).delete(cursor, user, type_ids, context=context)

Type()


class AccountTemplate(OSV):
    'Account Template'
    _name = 'account.account.template'
    _description = __doc__

    name = fields.Char('Name', size=None, required=True, translate=True,
            select=1)
    complete_name = fields.Function('get_complete_name', type='char',
            string='Code - Name', order_field='code')
    code = fields.Char('Code', size=None, select=1)
    type = fields.Many2One('account.account.type.template', 'Type',
            ondelete="restrict",
            states={
                'invisible': "kind == 'view'",
                'required': "kind != 'view'",
            })
    parent = fields.Many2One('account.account.template', 'Parent', select=1,
            ondelete="restrict")
    childs = fields.One2Many('account.account.template', 'parent', 'Childs')
    reconcile = fields.Boolean('Reconcile',
            states={
                'invisible': "kind == 'view'",
            })
    kind = fields.Selection([
        ('other', 'Other'),
        ('payable', 'Payable'),
        ('revenue', 'Revenue'),
        ('receivable', 'Receivable'),
        ('expense', 'Expense'),
        ('view', 'View'),
        ], 'Kind', required=True)
    deferral = fields.Boolean('Deferral', states={
        'invisible': "kind == 'view'",
        })

    def __init__(self):
        super(AccountTemplate, self).__init__()
        self._constraints += [
            ('check_recursion', 'recursive_accounts'),
        ]
        self._error_messages.update({
            'recursive_accounts': 'You can not create recursive accounts!',
        })
        self._order.insert(0, ('code', 'ASC'))
        self._order.insert(1, ('name', 'ASC'))

    def default_kind(self, cursor, user, context=None):
        return 'view'

    def default_reconcile(self, cursor, user, context=None):
        return False

    def default_deferral(self, cursor, user, context=None):
        return True

    def get_complete_name(self, cursor, user, ids, name, arg, context=None):
        res = self.name_get(cursor, user, ids, context=context)
        return dict(res)

    def name_search(self, cursor, user, name='', args=None, operator='ilike',
            context=None, limit=None):
        if name:
            ids = self.search(cursor, user,
                    [('code', 'like', name + '%')] + (args or []),
                    limit=limit, context=context)
            if not ids:
                ids = self.search(cursor, user,
                        [(self._rec_name, operator, name)] + (args or []),
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


    def _get_account_value(self, cursor, user, template, context=None):
        '''
        Set the values for account creation.

        :param cursor: the database cursor
        :param user: the user id
        :param template: the BrowseRecord of the template
        :param context: the context
        :return: a dictionary with account fields as key and values as value
        '''
        res = {}
        res['name'] = template.name
        res['code'] = template.code
        res['kind'] = template.kind
        res['reconcile'] = template.reconcile
        res['deferral'] = template.deferral
        return res

    def create_account(self, cursor, user, template, company_id, context=None,
            template2account=None, template2type=None, parent_id=False):
        '''
        Create recursively accounts based on template.

        :param cursor: the database cursor
        :param user: the user id
        :param template: the template id or the BrowseRecord of template
                used for account creation
        :param company_id: the id of the company for which accounts
                are created
        :param context: the context
        :param template2account: a dictionary with template id as key
                and account id as value, used to convert template id
                into account. The dictionary is filled with new accounts
        :param template2type: a dictionary with type template id as key
                and type id as value, used to convert type template id
                into type.
        :param parent_id: the account id of the parent of the accounts
                that must be created
        :return: id of the account created
        '''
        account_obj = self.pool.get('account.account')

        if template2account is None:
            template2account = {}

        if template2type is None:
            template2type = {}

        if isinstance(template, (int, long)):
            template = self.browse(cursor, user, template, context=context)

        if template.id not in template2account:
            vals = self._get_account_value(cursor, user, template, context=context)
            vals['company'] = company_id
            vals['parent'] = parent_id
            vals['type'] = template2type.get(template.type.id, False)

            new_id = account_obj.create(cursor, user, vals, context=context)
            template2account[template.id] = new_id
        else:
            new_id = template2account[template.id]

        new_childs = []
        for child in template.childs:
            new_childs.append(self.create_account(cursor, user, child,
                company_id, context=context, template2account=template2account,
                template2type=template2type, parent_id=new_id))
        return new_id

    def update_account_taxes(self, cursor, user, template, template2account,
            template2tax, context=None, template_done=None):
        '''
        Update recursively account taxes based on template.

        :param cursor: the database cursor
        :param user: the user id
        :param template: the template id or the BrowseRecord of template
            used for account creation
        :param template2account: a dictionary with template id as key
            and account id as value, used to convert template id into
            account.
        :param template2tax: a dictionary with tax template id as key
            and tax id as value, used to convert tax template id into
            tax.
        :param context: the context
        :param template_done: a list of template id already updated.
            The list is filled.
        '''
        account_obj = self.pool.get('account.account')

        if template2account is None:
            template2account = {}
        if template2tax is None:
            template2tax = {}
        if template_done is None:
            template_done = []

        if isinstance(template, (int, long)):
            template = self.browse(cursor, user, template, context=context)

        if template.id not in template_done:
            account_obj.write(cursor, user, template2account[template.id], {
                'taxes': [('add', template2tax[x.id]) for x in template.taxes],
                }, context=context)
            template_done.append(template.id)

        for child in template.childs:
            self.update_account_taxes(cursor, user, child, template2account,
                    template2tax, context=context, template_done=template_done)

AccountTemplate()


class Account(OSV):
    'Account'
    _name = 'account.account'
    _description = __doc__

    name = fields.Char('Name', size=None, required=True, translate=True,
            select=1)
    complete_name = fields.Function('get_complete_name', type='char',
            string='Code - Name', order_field='code')
    code = fields.Char('Code', size=None, select=1)
    active = fields.Boolean('Active', select=2)
    company = fields.Many2One('company.company', 'Company', required=True,
            ondelete="restrict")
    currency = fields.Function('get_currency', type='many2one',
            relation='currency.currency', string='Currency')
    currency_digits = fields.Function('get_currency_digits', type='integer',
            string='Currency Digits')
    second_currency = fields.Many2One('currency.currency', 'Secondary currency',
            help='Force all moves for this account \n' \
                    'to have this secondary currency.', ondelete="restrict")
    type = fields.Many2One('account.account.type', 'Type', ondelete="restrict",
            states={
                'invisible': "kind == 'view'",
                'required': "kind != 'view'",
            })
    parent = fields.Many2One('account.account', 'Parent', select=1,
            left="left", right="right", ondelete="restrict")
    left = fields.Integer('Left', required=True)
    right = fields.Integer('Right', required=True)
    childs = fields.One2Many('account.account', 'parent', 'Childs')
    balance = fields.Function('get_balance', digits="(16, currency_digits)",
            string='Balance')
    credit = fields.Function('get_credit_debit', digits="(16, currency_digits)",
            string='Credit')
    debit = fields.Function('get_credit_debit', digits="(16, currency_digits)",
            string='Debit')
    reconcile = fields.Boolean('Reconcile',
            help='Check if the account can be used \n' \
                    'for reconciliation.',
            states={
                'invisible': "kind == 'view'",
            })
    note = fields.Text('Note')
    kind = fields.Selection([
        ('other', 'Other'),
        ('payable', 'Payable'),
        ('revenue', 'Revenue'),
        ('receivable', 'Receivable'),
        ('expense', 'Expense'),
        ('view', 'View'),
        ], 'Kind', required=True)
    deferral = fields.Boolean('Deferral', states={
        'invisible': "kind == 'view'",
        })
    deferrals = fields.One2Many('account.account.deferral', 'account',
            'Deferrals', readonly=True, states={
                'invisible': "kind == 'view'",
            })

    def __init__(self):
        super(Account, self).__init__()
        self._constraints += [
            ('check_recursion', 'recursive_accounts'),
        ]
        self._error_messages.update({
            'recursive_accounts': 'You can not create recursive accounts!',
            'delete_account_with_move_line': 'You can not delete account ' \
                    'with move line!',
        })
        self._sql_error_messages.update({
            'parent_fkey': 'You can not delete account ' \
                    'that have children!',
        })
        self._order.insert(0, ('code', 'ASC'))
        self._order.insert(1, ('name', 'ASC'))

    def default_left(self, cursor, user, context=None):
        return 0

    def default_right(self, cursor, user, context=None):
        return 0

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

    def default_deferral(self, cursor, user, context=None):
        return True

    def default_kind(self, cursor, user, context=None):
        return 'view'

    def get_complete_name(self, cursor, user, ids, name, arg, context=None):
        res = self.name_get(cursor, user, ids, context=context)
        return dict(res)

    def get_currency(self, cursor, user, ids, name, arg, context=None):
        currency_obj = self.pool.get('currency.currency')
        res = {}
        for account in self.browse(cursor, user, ids, context=context):
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

    def get_currency_digits(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for account in self.browse(cursor, user, ids, context=context):
            res[account.id] = account.company.currency.digits
        return res

    def get_balance(self, cursor, user, ids, name, arg, context=None):
        res = {}
        company_obj = self.pool.get('company.company')
        currency_obj = self.pool.get('currency.currency')
        move_line_obj = self.pool.get('account.move.line')
        fiscalyear_obj = self.pool.get('account.fiscalyear')
        deferral_obj = self.pool.get('account.account.deferral')

        if context is None:
            context = {}

        query_ids, args_ids = self.search(cursor, user, [
            ('parent', 'child_of', ids),
            ], context=context, query_string=True)
        line_query, fiscalyear_ids = move_line_obj.query_get(cursor, user,
                context=context)
        cursor.execute('SELECT a.id, ' \
                    'SUM((COALESCE(l.debit, 0) - COALESCE(l.credit, 0))) ' \
                'FROM account_account a ' \
                    'LEFT JOIN account_move_line l ' \
                    'ON (a.id = l.account) ' \
                'WHERE a.kind != \'view\' ' \
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

        youngest_fiscalyear = None
        for fiscalyear in fiscalyear_obj.browse(cursor, user, fiscalyear_ids,
                context=context):
            if not youngest_fiscalyear \
                    or youngest_fiscalyear.start_date > fiscalyear.start_date:
                youngest_fiscalyear = fiscalyear

        fiscalyear = None
        if youngest_fiscalyear:
            fiscalyear_ids = fiscalyear_obj.search(cursor, user, [
                ('end_date', '<=', youngest_fiscalyear.start_date),
                ('company', '=', youngest_fiscalyear.company),
                ], order=[('end_date', 'DESC')], limit=1, context=context)
            if fiscalyear_ids:
                fiscalyear = fiscalyear_obj.browse(cursor, user,
                        fiscalyear_ids[0], context=context)

        if fiscalyear:
            if fiscalyear.state == 'close':
                deferral_ids = deferral_obj.search(cursor, user, [
                    ('fiscalyear', '=', fiscalyear.id),
                    ('account', 'in', ids),
                    ], context=context)
                id2deferral = {}
                for deferral in deferral_obj.browse(cursor, user, deferral_ids,
                        context=context):
                    id2deferral[deferral.account.id] = deferral

                for account_id in ids:
                    if account_id in id2deferral:
                        deferral = id2deferral[account_id]
                        res[account_id] += deferral.debit - deferral.credit
            else:
                ctx = context.copy()
                ctx['fiscalyear'] = fiscalyear.id
                if 'date' in context:
                    del context['date']
                res2 = self.get_balance(cursor, user, ids, name, arg,
                        context=ctx)
                for account_id in ids:
                    res[account_id] += res2[account_id]

        for account_id in ids:
            company_id = account2company[account_id]
            to_currency = id2company[company_id].currency
            res[account_id] = currency_obj.round(cursor, user, to_currency,
                    res[account_id])
        return res

    def get_credit_debit(self, cursor, user, ids, names, arg, context=None):
        '''
        Function to compute debit, credit for account ids.

        :param cursor: the database cursor
        :param user: the user id
        :param ids: the ids of the account
        :param names: the list of field name to compute
        :param arg: optional argument
        :param context: the context
        :return: a dictionary with all field names as key and
            a dictionary as value with id as key
        '''
        res = {}
        move_line_obj = self.pool.get('account.move.line')
        company_obj = self.pool.get('company.company')
        currency_obj = self.pool.get('currency.currency')
        fiscalyear_obj = self.pool.get('account.fiscalyear')
        deferral_obj = self.pool.get('account.account.deferral')

        if context is None:
            context = {}

        for name in names:
            if name not in ('credit', 'debit'):
                raise Exception('Bad argument')
            res[name] = {}

        line_query, fiscalyear_ids = move_line_obj.query_get(cursor, user,
                context=context)
        for i in range(0, len(ids), cursor.IN_MAX):
            sub_ids = ids[i:i + cursor.IN_MAX]
            cursor.execute('SELECT a.id, ' + \
                        ','.join(['SUM(COALESCE(l.' + name + ', 0))'
                            for name in names]) + ' ' \
                    'FROM account_account a ' \
                        'LEFT JOIN account_move_line l ' \
                        'ON (a.id = l.account) ' \
                    'WHERE a.kind != \'view\' ' \
                        'AND a.id IN (' + \
                            ','.join(['%s' for x in sub_ids]) + ') ' \
                        'AND ' + line_query + ' ' \
                        'AND a.active ' \
                    'GROUP BY a.id', sub_ids)
            for row in cursor.fetchall():
                account_id = row[0]
                for i in range(len(names)):
                    res[names[i]][account_id] = row[i + 1]

        account2company = {}
        id2company = {}
        accounts = self.browse(cursor, user, ids, context=context)
        for account in accounts:
            account2company[account.id] = account.company.id
            id2company[account.company.id] = account.company

        for account_id in ids:
            for name in names:
                res[name].setdefault(account_id, Decimal('0.0'))

        youngest_fiscalyear = None
        for fiscalyear in fiscalyear_obj.browse(cursor, user, fiscalyear_ids,
                context=context):
            if not youngest_fiscalyear \
                    or youngest_fiscalyear.start_date > fiscalyear.start_date:
                youngest_fiscalyear = fiscalyear

        fiscalyear = None
        if youngest_fiscalyear:
            fiscalyear_ids = fiscalyear_obj.search(cursor, user, [
                ('end_date', '<=', youngest_fiscalyear.start_date),
                ('company', '=', youngest_fiscalyear.company),
                ], order=[('end_date', 'DESC')], limit=1, context=context)
            if fiscalyear_ids:
                fiscalyear = fiscalyear_obj.browse(cursor, user,
                        fiscalyear_ids[0], context=context)

        if fiscalyear:
            if fiscalyear.state == 'close':
                deferral_ids = deferral_obj.search(cursor, user, [
                    ('fiscalyear', '=', fiscalyear.id),
                    ('account', 'in', ids),
                    ], context=context)
                id2deferral = {}
                for deferral in deferral_obj.browse(cursor, user, deferral_ids,
                        context=context):
                    id2deferral[deferral.account.id] = deferral

                for account_id in ids:
                    if account_id in id2deferral:
                        deferral = id2deferral[account_id]
                        for name in names:
                            res[name][account_id] += deferral[name]
            else:
                ctx = context.copy()
                ctx['fiscalyear'] = fiscalyear.id
                if 'date' in ctx:
                    del ctx['date']
                res2 = self.get_credit_debit(cursor, user, ids, names, arg,
                        context=ctx)
                for account_id in ids:
                    for name in names:
                        res[name][account_id] += res2[name][account_id]

        for account_id in ids:
            company_id = account2company[account_id]
            currency = id2company[company_id].currency
            for name in names:
                res[name][account_id] = currency_obj.round(cursor, user,
                        currency, res[name][account_id])
        return res

    def name_search(self, cursor, user, name='', args=None, operator='ilike',
            context=None, limit=None):
        if name:
            ids = self.search(cursor, user,
                    [('code', 'like', name + '%')] + (args or []),
                    limit=limit, context=context)
            if not ids:
                ids = self.search(cursor, user,
                        [(self._rec_name, operator, name)] + (args or []),
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

    def copy(self, cursor, user, ids, default=None, context=None):
        if default is None:
            default = {}
        default['left'] = 0
        default['right'] = 0
        res = super(Account, self).copy(cursor, user, ids, default=default,
                context=context)
        self._rebuild_tree(cursor, user, 'parent', False, 0)
        return res

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

    def delete(self, cursor, user, ids, context=None):
        move_line_obj = self.pool.get('account.move.line')
        if isinstance(ids, (int, long)):
            ids = [ids]
        account_ids = self.search(cursor, user, [
            ('parent', 'child_of', ids),
            ], context=context)
        if move_line_obj.search(cursor, user, [
            ('account', 'in', account_ids),
            ], context=context):
            self.raise_user_error(cursor, 'delete_account_with_move_line',
                    context=context)
        return super(Account, self).delete(cursor, user, account_ids,
                context=context)

Account()


class AccountDeferral(OSV):
    '''
    Account Deferral

    It is used to deferral the debit/credit of account by fiscal year.
    '''
    _name = 'account.account.deferral'
    _description = 'Account Deferral'

    account = fields.Many2One('account.account', 'Account', required=True,
            select=1)
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
            required=True, select=1)
    debit = fields.Numeric('Debit', digits="(16, currency_digits)")
    credit = fields.Numeric('Credit', digits="(16, currency_digits)")
    currency_digits = fields.Function('get_currency_digits', type='integer',
            string='Currency Digits')

    def __init__(self):
        super(AccountDeferral, self).__init__()
        self._sql_constraints += [
            ('deferral_uniq', 'UNIQUE(account, fiscalyear)',
                'Deferral must be unique by account and fiscal year'),
        ]
        self._error_messages.update({
            'write_deferral': 'You can not modify Account Deferral records',
            })

    def get_currency_digits(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for deferral in self.browse(cursor, user, ids, context=context):
            res[deferral.id] = deferral.account.currency_digits
        return res

    def name_get(self, cursor, user, ids, context=None):
        if not ids:
            return []
        if isinstance(ids, (int, long)):
            ids = [ids]
        return [(r.id, r.account.name + ' - ' + r.fiscalyear.name) for r in
                self.browse(cursor, user, ids, context=context)]

    def name_search(self, cursor, user, name='', args=None, operator='ilike',
            context=None, limit=None):
        if args is None:
            args = []
        args = args[:]
        if name:
            args = ['AND', args, ['OR', ('account.name', operator, name),
                ('fiscalyear.name', operator, name)]]
        ids = self.search(cursor, user, args, limit=limit, context=context)
        res = self.name_get(cursor, user, ids, context=context)
        return res

    def write(self, cursor, user, ids, vals, context=None):
        self.raise_user_error(cursor, 'write_deferral', context=context)

AccountDeferral()


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
            ('inherit', '=', False),
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
            ('kind', '!=', 'view'),
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
            if datas['form']['end_period'] not in end_period_ids:
                end_period_ids.append(datas['form']['end_period'])
        else:
            end_period_ids = period_obj.search(cursor, user, [
                ('fiscalyear', '=', datas['form']['fiscalyear']),
                ], context=context)

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
                account_id, list(set(end_period_ids).difference(
                    set(start_period_ids))), datas['form']['posted'], context)
        context['company'] = company

        return super(GeneralLegder, self).parse(cursor, user, report, objects,
                datas, context)

    def lines(self, cursor, user, account_id, period_ids, posted, context):
        move_line_obj = self.pool.get('account.move.line')
        move_obj = self.pool.get('account.move')
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

        state_selections = dict(move_obj.fields_get(cursor, user,
                fields_names=['state'], context=context)['state']['selection'])

        balance = Decimal('0.0')
        for line in move_lines:
            balance += line.debit - line.credit
            res.append({
                'date': line.date,
                'debit': line.debit,
                'credit': line.credit,
                'balance': balance,
                'name': line.name,
                'state': state_selections.get(line.move.state, line.move.state),
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
        date_obj = self.pool.get('ir.date')
        return date_obj.today(cursor, user, context=context)

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
        lang_obj = self.pool.get('ir.lang')

        company = company_obj.browse(cursor, user, datas['form']['company'],
                context=context)
        for code in [context.get('language', False) or 'en_US', 'en_US']:
            lang_ids = lang_obj.search(cursor, user, [
                ('code', '=', code),
                ], context=context)
            if lang_ids:
                break
        lang = lang_obj.browse(cursor, user, lang_ids[0], context=context)

        date = mx.DateTime.strptime(str(datas['form']['date']), '%Y-%m-%d')
        date = date.strftime(lang.date)

        model_data_ids = model_data_obj.search(cursor, user, [
            ('fs_id', '=', 'act_account_balance_sheet_tree'),
            ('module', '=', 'account'),
            ('inherit', '=', False),
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
            ('inherit', '=', False),
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
        account_type_template_obj = \
                self.pool.get('account.account.type.template')
        account_template_obj = self.pool.get('account.account.template')
        tax_code_template_obj = self.pool.get('account.tax.code.template')
        tax_template_obj = self.pool.get('account.tax.template')

        account_template = account_template_obj.browse(cursor, user,
                datas['form']['account_template'], context=context)

        template2type = {}
        account_type_template_obj.create_type(cursor, user,
                account_template.type, datas['form']['company'],
                context=context, template2type=template2type)

        template2account = {}
        account_template_obj.create_account(cursor, user,
                account_template, datas['form']['company'],
                context=context, template2account=template2account,
                template2type=template2type)

        template2tax_code = {}
        tax_code_template_ids = tax_code_template_obj.search(cursor, user, [
            ('account', '=', datas['form']['account_template']),
            ('parent', '=', False),
            ], context=context)
        for tax_code_template in tax_code_template_obj.browse(cursor, user,
                tax_code_template_ids, context=context):
            tax_code_template_obj.create_tax_code(cursor, user,
                    tax_code_template, datas['form']['company'],
                    context=context, template2tax_code=template2tax_code)

        template2tax = {}
        tax_template_ids = tax_template_obj.search(cursor, user, [
            ('account', '=', datas['form']['account_template']),
            ('parent', '=', False),
            ], context=context)
        for tax_template in tax_template_obj.browse(cursor, user,
                tax_template_ids, context=context):
            tax_template_obj.create_tax(cursor, user, tax_template,
                    datas['form']['company'],
                    template2tax_code=template2tax_code,
                    template2account=template2account,
                    context=context, template2tax=template2tax)

        account_template_obj.update_account_taxes(cursor, user,
                account_template, template2account, template2tax, context=context)

        return {'company': datas['form']['company']}

    def _action_create_properties(self, cursor, user, datas, context=None):
        property_obj = self.pool.get('ir.property')
        model_field_obj = self.pool.get('ir.model.field')

        account_receivable_field_id = model_field_obj.search(cursor, user, [
            ('model.model', '=', 'party.party'),
            ('name', '=', 'account_receivable'),
            ], limit=1, context=context)[0]
        property_ids = property_obj.search(cursor, user, [
            ('field', '=', account_receivable_field_id),
            ('res', '=', False),
            ('company', '=', datas['form']['company']),
            ], context=context)
        property_obj.delete(cursor, 0, property_ids, context=context)
        property_obj.create(cursor, 0, {
            'name': 'account_receivable',
            'field': account_receivable_field_id,
            'value': 'account.account,' + \
                    str(datas['form']['account_receivable']),
            'company': datas['form']['company'],
            }, context=context)

        account_payable_field_id = model_field_obj.search(cursor, user, [
            ('model.model', '=', 'party.party'),
            ('name', '=', 'account_payable'),
            ], limit=1, context=context)[0]
        property_ids = property_obj.search(cursor, user, [
            ('field', '=', account_payable_field_id),
            ('res', '=', False),
            ('company', '=', datas['form']['company']),
            ], context=context)
        property_obj.delete(cursor, 0, property_ids, context=context)
        property_obj.create(cursor, 0, {
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

    def parse(self, cursor, user, report, objects, datas, context):
        party_obj = self.pool.get('party.party')
        move_line_obj = self.pool.get('account.move.line')
        company_obj = self.pool.get('company.company')
        date_obj = self.pool.get('ir.date')
        context = context.copy()

        company = company_obj.browse(cursor, user,
                datas['form']['company'], context=context)
        context['company'] = company
        context['digits'] = company.currency.digits
        context['fiscalyear'] = datas['form']['fiscalyear']
        line_query, _ = move_line_obj.query_get(cursor, user, context=context)
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
                       (datas['form']['company'], date_obj.today(cursor, user,
                           context=context)))

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

        return super(ThirdPartyBalance, self).parse(cursor, user, report,
                objects, datas, context)

ThirdPartyBalance()


class OpenAgedBalanceInit(WizardOSV):
    _name = 'account.account.open_aged_balance.init'
    company = fields.Many2One('company.company', 'Company', required=True)
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
            required=True)
    balance_type = fields.Selection(
        [('customer', 'Customer'), ('supplier', 'Supplier'), ('both', 'Both')],
        "Type", required=True)
    term1 = fields.Integer("First Term", required=True)
    term2 = fields.Integer("Second Term", required=True)
    term3 = fields.Integer("Third Term", required=True)
    unit = fields.Selection(
        [('day', 'Day'), ('month', 'Month')], "Unit", required=True)
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

    def default_balance_type(self, cursor, user, context=None):
        return "customer"

    def default_posted(self, cursor, user, context=None):
        return False

    def default_term1(self, cursor, user, context=None):
        return 30

    def default_term2(self, cursor, user, context=None):
        return 60

    def default_term3(self, cursor, user, context=None):
        return 90

    def default_unit(self, cursor, user, context=None):
        return 'day'

    def default_company(self, cursor, user, context=None):
        if context is None:
            context = {}
        company_obj = self.pool.get('company.company')
        if context.get('company'):
            return company_obj.name_get(cursor, user, context['company'],
                    context=context)[0]
        return False

OpenAgedBalanceInit()


class OpenAgedBalance(Wizard):
    'Open Aged Party Balance'
    _name = 'account.account.open_aged_balance'

    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'account.account.open_aged_balance.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('print', 'Print', 'tryton-ok', True),
                ],
            },
        },
        'print': {
            'actions': ['check',],
            'result': {
                'type': 'print',
                'report': 'account.account.aged_balance',
                'state': 'end',
            },
        },
    }

    def __init__(self):
        super(OpenAgedBalance, self).__init__()
        self._error_messages.update({
                'warning': 'Warning',
                'term_overlap_desc': 'You cannot define overlapping terms'})

    def check(self, cursor, user, datas, context=None):
        if not (datas['form']['term1'] < datas['form']['term2'] \
                  < datas['form']['term3']):
            self.raise_user_error(cursor, error="warning",
                                  error_description="term_overlap_desc")
        return datas['form']

OpenAgedBalance()


class AgedBalance(Report):
    _name = 'account.account.aged_balance'

    def parse(self, cursor, user, report, objects, datas, context):
        party_obj = self.pool.get('party.party')
        move_line_obj = self.pool.get('account.move.line')
        company_obj = self.pool.get('company.company')
        date_obj = self.pool.get('ir.date')

        company = company_obj.browse(cursor, user,
                datas['form']['company'], context=context)
        context['digits'] = company.currency.digits
        context['fiscalyear'] = datas['form']['fiscalyear']
        context['posted'] = datas['form']['posted']
        line_query, _ = move_line_obj.query_get(cursor, user, context=context)

        terms = (datas['form']['term1'],
                  datas['form']['term2'],
                  datas['form']['term3'])
        if datas['form']['unit'] == 'month':
            coef = 30
        else:
            coef = 1

        kind = {'both': ('payable','receivable'),
                'supplier': ('payable',),
                'customer': ('receivable',),
                }[datas['form']['balance_type']]

        res = {}
        for position,term in enumerate(terms):
            if position == 0:
                term_query = '(l.maturity_date <= %s '\
                    'OR l.maturity_date IS NULL) '
                term_args = (date_obj.today(cursor, user, context=context) + \
                    datetime.timedelta(days=term*coef),)
            else:
                term_query = '(l.maturity_date <= %s '\
                    'AND l.maturity_date >= %s) '
                term_args = (
                    date_obj.today(cursor, user, context=context) + \
                        datetime.timedelta(days=term*coef),
                    date_obj.today(cursor, user, context=context) + \
                        datetime.timedelta(days=terms[position-1]*coef),
                    )

            cursor.execute(
                'SELECT l.party, SUM(l.debit) - SUM(l.credit) ' \
                  'FROM account_move_line l ' \
                  'JOIN account_move m on (l.move = m.id) '
                  'JOIN account_account a on (l.account = a.id) '
                'WHERE l.party is not null '\
                  'AND a.active ' \
                  'AND a.kind in ('+ ','.join('%s' for i in kind) + ") "\
                  'AND l.reconciliation IS NULL ' \
                  'AND a.company = %s ' \
                  'AND '+ term_query+\
                  'AND ' + line_query + ' ' \
                  'GROUP BY l.party',
                kind + (datas['form']['company'],) + term_args)
            for party, solde in cursor.fetchall():
                if party in res:
                    res[party][position] = solde
                else:
                    res[party] = [i[0] == position and solde or Decimal("0.0")\
                                      for i in enumerate(terms)]
        parties = party_obj.name_get(
                cursor, user, [k for k in res.iterkeys()], context=context)
        parties.sort(lambda x,y: cmp(x[1],y[1]))

        context['main_title'] = datas['form']['balance_type']
        context['unit'] = datas['form']['unit']
        for i in range(3):
            context['total' + str(i)] = sum((v[i] for v in res.itervalues()))
            context['term' + str(i)] = terms[i]

        context['company'] = company
        context['parties']= ({'name': p[1],
                              'amount0': res[p[0]][0],
                              'amount1': res[p[0]][1],
                              'amount2': res[p[0]][2],
                              } for p in parties)

        return super(AgedBalance, self).parse(cursor, user, report, objects,
                datas, context)

AgedBalance()
