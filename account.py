#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
import datetime
import time
import os
import operator
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard
from trytond.report import Report
from trytond.tools import reduce_ids
from trytond.pyson import Eval, PYSONEncoder, Date
from trytond.transaction import Transaction
from trytond.pool import Pool


class TypeTemplate(ModelSQL, ModelView):
    'Account Type Template'
    _name = 'account.account.type.template'
    _description = __doc__
    name = fields.Char('Name', required=True, translate=True)
    parent = fields.Many2One('account.account.type.template', 'Parent',
            ondelete="RESTRICT")
    childs = fields.One2Many('account.account.type.template', 'parent', 'Children')
    sequence = fields.Integer('Sequence', required=True)
    balance_sheet = fields.Boolean('Balance Sheet')
    income_statement = fields.Boolean('Income Statement')
    display_balance = fields.Selection([
        ('debit-credit', 'Debit - Credit'),
        ('credit-debit', 'Credit - Debit'),
        ], 'Display Balance', required=True)

    def __init__(self):
        super(TypeTemplate, self).__init__()
        self._constraints += [
            ('check_recursion', 'recursive_types'),
        ]
        self._error_messages.update({
            'recursive_types': 'You can not create recursive types!',
        })
        self._order.insert(0, ('sequence', 'ASC'))

    def default_balance_sheet(self):
        return False

    def default_income_statement(self):
        return False

    def default_display_balance(self):
        return 'debit-credit'

    def get_rec_name(self, ids, name):
        if not ids:
            return {}
        res = {}
        def _name(type):
            if type.parent:
                return _name(type.parent) + '\\' + type.name
            else:
                return type.name
        for type in self.browse(ids):
            res[type.id] = _name(type)
        return res

    def _get_type_value(self, template, type=None):
        '''
        Set the values for account creation.

        :param template: the BrowseRecord of the template
        :param type: the BrowseRecord of the type to update
        :return: a dictionary with account fields as key and values as value
        '''
        res = {}
        if not type or type.name != template.name:
            res['name'] = template.name
        if not type or type.sequence != template.sequence:
            res['sequence'] = template.sequence
        if not type or type.balance_sheet != template.balance_sheet:
            res['balance_sheet'] = template.balance_sheet
        if not type or type.income_statement != template.income_statement:
            res['income_statement'] = template.income_statement
        if not type or type.display_balance != template.display_balance:
            res['display_balance'] = template.display_balance
        if not type or type.template.id != template.id:
            res['template'] = template.id
        return res

    def create_type(self, template, company_id, template2type=None,
            parent_id=False):
        '''
        Create recursively types based on template.

        :param template: the template id or the BrowseRecord of the template
                used for type creation
        :param company_id: the id of the company for which types are created
        :param template2type: a dictionary with template id as key
                and type id as value, used to convert template id
                into type. The dictionary is filled with new types
        :param parent_id: the type id of the parent of the types that must
                be created
        :return: id of the type created
        '''
        type_obj = Pool().get('account.account.type')
        lang_obj = Pool().get('ir.lang')

        if template2type is None:
            template2type = {}

        if isinstance(template, (int, long)):
            template = self.browse(template)

        if template.id not in template2type:
            vals = self._get_type_value(template)
            vals['company'] = company_id
            vals['parent'] = parent_id

            new_id = type_obj.create(vals)

            prev_lang = template._context.get('language') or 'en_US'
            prev_data = {}
            for field_name, field in template._columns.iteritems():
                if getattr(field, 'translate', False):
                    prev_data[field_name] = template[field_name]
            for lang in lang_obj.get_translatable_languages():
                if lang == prev_lang:
                    continue
                template.setLang(lang)
                data = {}
                for field_name, field in template._columns.iteritems():
                    if getattr(field, 'translate', False) \
                            and template[field_name] != prev_data[field_name]:
                        data[field_name] = template[field_name]
                if data:
                    with Transaction().set_context(language=lang):
                        type_obj.write(new_id, data)
            template.setLang(prev_lang)
            template2type[template.id] = new_id
        else:
            new_id = template2type[template.id]

        new_childs = []
        for child in template.childs:
            new_childs.append(self.create_type(child, company_id,
                template2type=template2type, parent_id=new_id))
        return new_id

TypeTemplate()


class Type(ModelSQL, ModelView):
    'Account Type'
    _name = 'account.account.type'
    _description = __doc__
    name = fields.Char('Name', size=None, required=True, translate=True)
    parent = fields.Many2One('account.account.type', 'Parent',
        ondelete="RESTRICT", domain=[
            ('company', '=', Eval('company')),
            ], depends=['company'])
    childs = fields.One2Many('account.account.type', 'parent', 'Children',
        domain=[
            ('company', '=', Eval('company')),
        ], depends=['company'])
    sequence = fields.Integer('Sequence', required=True,
            help='Use to order the account type')
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
            'get_currency_digits')
    amount = fields.Function(fields.Numeric('Amount',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits']),
        'get_amount')
    balance_sheet = fields.Boolean('Balance Sheet')
    income_statement = fields.Boolean('Income Statement')
    display_balance = fields.Selection([
        ('debit-credit', 'Debit - Credit'),
        ('credit-debit', 'Credit - Debit'),
        ], 'Display Balance', required=True)
    company = fields.Many2One('company.company', 'Company', required=True,
            ondelete="RESTRICT")
    template = fields.Many2One('account.account.type.template', 'Template')

    def __init__(self):
        super(Type, self).__init__()
        self._constraints += [
            ('check_recursion', 'recursive_types'),
        ]
        self._error_messages.update({
            'recursive_types': 'You can not create recursive types!',
        })
        self._order.insert(0, ('sequence', 'ASC'))

    def default_balance_sheet(self):
        return False

    def default_income_statement(self):
        return False

    def default_display_balance(self):
        return 'debit-credit'

    def get_currency_digits(self, ids, name):
        res = {}
        for type in self.browse(ids):
            res[type.id] = type.company.currency.digits
        return res

    def get_amount(self, ids, name):
        account_obj = Pool().get('account.account')
        currency_obj = Pool().get('currency.currency')

        res = {}
        for type_id in ids:
            res[type_id] = Decimal('0.0')

        child_ids = self.search([
            ('parent', 'child_of', ids),
            ])
        type_sum = {}
        for type_id in child_ids:
            type_sum[type_id] = Decimal('0.0')

        account_ids = account_obj.search([
            ('type', 'in', child_ids),
            ])
        for account in account_obj.browse(account_ids):
            type_sum[account.type.id] += currency_obj.round(
                    account.company.currency, account.debit - account.credit)

        types = self.browse(ids)
        for type in types:
            child_ids = self.search([
                ('parent', 'child_of', [type.id]),
                ])
            for child_id in child_ids:
                res[type.id] += type_sum[child_id]
            res[type.id] = currency_obj.round(type.company.currency,
                    res[type.id])
            if type.display_balance == 'credit-debit':
                res[type.id] = - res[type.id]
        return res

    def get_rec_name(self, ids, name):
        if not ids:
            return {}
        res = {}
        def _name(type):
            if type.parent:
                return _name(type.parent) + '\\' + type.name
            else:
                return type.name
        for type in self.browse(ids):
            res[type.id] = _name(type)
        return res

    def delete(self, ids):
        if isinstance(ids, (int, long)):
            ids = [ids]
        type_ids = self.search([
            ('parent', 'child_of', ids),
            ])
        return super(Type, self).delete(type_ids)

    def update_type(self, type, template2type=None):
        '''
        Update recursively types based on template.

        :param type: a type id or the BrowseRecord of the type
        :param template2type: a dictionary with template id as key
                and type id as value, used to convert template id
                into type. The dictionary is filled with new types
        '''
        template_obj = Pool().get('account.account.type.template')
        lang_obj = Pool().get('ir.lang')

        if template2type is None:
            template2type = {}

        if isinstance(type, (int, long)):
            type = self.browse(type)

        if type.template:
            vals = template_obj._get_type_value(type.template, type=type)
            if vals:
                self.write(type.id, vals)

            prev_lang = type._context.get('language') or 'en_US'
            prev_data = {}
            for field_name, field in type.template._columns.iteritems():
                if getattr(field, 'translate', False):
                    prev_data[field_name] = type.template[field_name]
            for lang in lang_obj.get_translatable_languages():
                if lang == prev_lang:
                    continue
                type.setLang(lang)
                data = {}
                for field_name, field in type.template._columns.iteritems():
                    if (getattr(field, 'translate', False)
                            and type.template[field_name] !=
                            prev_data[field_name]):
                        data[field_name] = type.template[field_name]
                if data:
                    with Transaction().set_context(language=lang):
                        self.write(type.id, data)
            type.setLang(prev_lang)
            template2type[type.template.id] = type.id

        for child in type.childs:
            self.update_type(child, template2type=template2type)

Type()


class AccountTemplate(ModelSQL, ModelView):
    'Account Template'
    _name = 'account.account.template'
    _description = __doc__

    name = fields.Char('Name', size=None, required=True, translate=True,
            select=1)
    code = fields.Char('Code', size=None, select=1)
    type = fields.Many2One('account.account.type.template', 'Type',
        ondelete="RESTRICT",
        states={
            'invisible': Eval('kind') == 'view',
            'required': Eval('kind') != 'view',
            }, depends=['kind'])
    parent = fields.Many2One('account.account.template', 'Parent', select=1,
            ondelete="RESTRICT")
    childs = fields.One2Many('account.account.template', 'parent', 'Children')
    reconcile = fields.Boolean('Reconcile',
        states={
            'invisible': Eval('kind') == 'view',
            }, depends=['kind'])
    kind = fields.Selection([
        ('other', 'Other'),
        ('payable', 'Payable'),
        ('revenue', 'Revenue'),
        ('receivable', 'Receivable'),
        ('expense', 'Expense'),
        ('view', 'View'),
        ], 'Kind', required=True)
    deferral = fields.Boolean('Deferral', states={
            'invisible': Eval('kind') == 'view',
            }, depends=['kind'])

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

    def default_kind(self):
        return 'view'

    def default_reconcile(self):
        return False

    def default_deferral(self):
        return True

    def get_rec_name(self, ids, name):
        if not ids:
            return {}
        res = {}
        for template in self.browse(ids):
            if template.code:
                res[template.id] = template.code + ' - ' + template.name
            else:
                res[template.id] = template.name
        return res

    def search_rec_name(self, name, clause):
        ids = self.search([
            ('code',) + clause[1:],
            ], limit=1)
        if ids:
            return [('code',) + clause[1:]]
        return [(self._rec_name,) + clause[1:]]

    def _get_account_value(self, template, account=None):
        '''
        Set the values for account creation.

        :param template: the BrowseRecord of the template
        :param account: the BrowseRecord of the account to update
        :return: a dictionary with account fields as key and values as value
        '''
        res = {}
        if not account or account.name != template.name:
            res['name'] = template.name
        if not account or account.code != template.code:
            res['code'] = template.code
        if not account or account.kind != template.kind:
            res['kind'] = template.kind
        if not account or account.reconcile != template.reconcile:
            res['reconcile'] = template.reconcile
        if not account or account.deferral != template.deferral:
            res['deferral'] = template.deferral
        if not account or account.template.id != template.id:
            res['template'] = template.id
        return res

    def create_account(self, template, company_id, template2account=None,
            template2type=None, parent_id=False):
        '''
        Create recursively accounts based on template.

        :param template: the template id or the BrowseRecord of template
                used for account creation
        :param company_id: the id of the company for which accounts
                are created
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
        account_obj = Pool().get('account.account')
        lang_obj = Pool().get('ir.lang')

        if template2account is None:
            template2account = {}

        if template2type is None:
            template2type = {}

        if isinstance(template, (int, long)):
            template = self.browse(template)

        if template.id not in template2account:
            vals = self._get_account_value(template)
            vals['company'] = company_id
            vals['parent'] = parent_id
            vals['type'] = template2type.get(template.type.id, False)

            new_id = account_obj.create(vals)

            prev_lang = template._context.get('language') or 'en_US'
            prev_data = {}
            for field_name, field in template._columns.iteritems():
                if getattr(field, 'translate', False):
                    prev_data[field_name] = template[field_name]
            for lang in lang_obj.get_translatable_languages():
                if lang == prev_lang:
                    continue
                template.setLang(lang)
                data = {}
                for field_name, field in template._columns.iteritems():
                    if getattr(field, 'translate', False) \
                            and template[field_name] != prev_data[field_name]:
                        data[field_name] = template[field_name]
                if data:
                    with Transaction().set_context(language=lang):
                        account_obj.write(new_id, data)
            template.setLang(prev_lang)
            template2account[template.id] = new_id
        else:
            new_id = template2account[template.id]

        new_childs = []
        for child in template.childs:
            new_childs.append(self.create_account(child, company_id,
                template2account=template2account, template2type=template2type,
                parent_id=new_id))
        return new_id

    def update_account_taxes(self, template, template2account, template2tax,
            template_done=None):
        '''
        Update recursively account taxes based on template.

        :param template: the template id or the BrowseRecord of template
            used for account creation
        :param template2account: a dictionary with template id as key
            and account id as value, used to convert template id into
            account.
        :param template2tax: a dictionary with tax template id as key
            and tax id as value, used to convert tax template id into
            tax.
        :param template_done: a list of template id already updated.
            The list is filled.
        '''
        account_obj = Pool().get('account.account')

        if template2account is None:
            template2account = {}
        if template2tax is None:
            template2tax = {}
        if template_done is None:
            template_done = []

        if isinstance(template, (int, long)):
            template = self.browse(template)

        if template.id not in template_done:
            if template.taxes:
                account_obj.write(template2account[template.id], {
                    'taxes': [
                        ('add', template2tax[x.id]) for x in template.taxes],
                    })
            template_done.append(template.id)

        for child in template.childs:
            self.update_account_taxes(child, template2account, template2tax,
                    template_done=template_done)

AccountTemplate()


class Account(ModelSQL, ModelView):
    'Account'
    _name = 'account.account'
    _description = __doc__

    name = fields.Char('Name', size=None, required=True, translate=True,
            select=1)
    code = fields.Char('Code', size=None, select=1)
    active = fields.Boolean('Active', select=2)
    company = fields.Many2One('company.company', 'Company', required=True,
            ondelete="RESTRICT")
    currency = fields.Function(fields.Many2One('currency.currency',
        'Currency'), 'get_currency')
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
            'get_currency_digits')
    second_currency = fields.Many2One('currency.currency', 'Secondary currency',
            help='Force all moves for this account \n' \
                    'to have this secondary currency.', ondelete="RESTRICT")
    type = fields.Many2One('account.account.type', 'Type', ondelete="RESTRICT",
        states={
            'invisible': Eval('kind') == 'view',
            'required': Eval('kind') != 'view',
            },
        domain=[
            ('company', '=', Eval('company')),
            ], depends=['kind', 'company'])
    parent = fields.Many2One('account.account', 'Parent', select=1,
            left="left", right="right", ondelete="RESTRICT")
    left = fields.Integer('Left', required=True, select=1)
    right = fields.Integer('Right', required=True, select=1)
    childs = fields.One2Many('account.account', 'parent', 'Children')
    balance = fields.Function(fields.Numeric('Balance',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits']),
        'get_balance')
    credit = fields.Function(fields.Numeric('Credit',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits']),
        'get_credit_debit')
    debit = fields.Function(fields.Numeric('Debit',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits']),
        'get_credit_debit')
    reconcile = fields.Boolean('Reconcile',
        help='Allow move lines of this account \n' \
            'to be reconciled.',
        states={
            'invisible': Eval('kind') == 'view',
            }, depends=['kind'])
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
            'invisible': Eval('kind') == 'view',
            }, depends=['kind'])
    deferrals = fields.One2Many('account.account.deferral', 'account',
        'Deferrals', readonly=True, states={
            'invisible': Eval('kind') == 'view',
            }, depends=['kind'])
    template = fields.Many2One('account.account.template', 'Template')

    def __init__(self):
        super(Account, self).__init__()
        self._constraints += [
            ('check_recursion', 'recursive_accounts'),
        ]
        self._error_messages.update({
            'recursive_accounts': 'You can not create recursive accounts!',
            'delete_account_containing_move_lines': 'You can not delete ' \
                    'accounts containing move lines!',
        })
        self._sql_error_messages.update({
            'parent_fkey': 'You can not delete accounts ' \
                    'that have children!',
        })
        self._order.insert(0, ('code', 'ASC'))
        self._order.insert(1, ('name', 'ASC'))

    def default_left(self):
        return 0

    def default_right(self):
        return 0

    def default_active(self):
        return True

    def default_company(self):
        return Transaction().context.get('company') or False

    def default_reconcile(self):
        return False

    def default_deferral(self):
        return True

    def default_kind(self):
        return 'view'

    def get_currency(self, ids, name):
        currency_obj = Pool().get('currency.currency')
        res = {}
        for account in self.browse(ids):
            res[account.id] = account.company.currency.id
        return res

    def get_currency_digits(self, ids, name):
        res = {}
        for account in self.browse(ids):
            res[account.id] = account.company.currency.digits
        return res

    def get_balance(self, ids, name):
        res = {}
        pool = Pool()
        company_obj = pool.get('company.company')
        currency_obj = pool.get('currency.currency')
        move_line_obj = pool.get('account.move.line')
        fiscalyear_obj = pool.get('account.fiscalyear')
        deferral_obj = pool.get('account.account.deferral')
        cursor = Transaction().cursor

        query_ids, args_ids = self.search([
            ('parent', 'child_of', ids),
            ], query_string=True)
        line_query, fiscalyear_ids = move_line_obj.query_get()
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
            # SQLite uses float for SUM
            if not isinstance(sum, Decimal):
                sum = Decimal(str(sum))
            account_sum[account_id] = sum

        account2company = {}
        id2company = {}
        id2account = {}
        all_ids = self.search([('parent', 'child_of', ids)])
        accounts = self.browse(all_ids)
        for account in accounts:
            account2company[account.id] = account.company.id
            id2company[account.company.id] = account.company
            id2account[account.id] = account

        for account_id in ids:
            res.setdefault(account_id, Decimal('0.0'))
            child_ids = self.search([
                ('parent', 'child_of', [account_id]),
                ])
            company_id = account2company[account_id]
            to_currency = id2company[company_id].currency
            for child_id in child_ids:
                child_company_id = account2company[child_id]
                from_currency = id2company[child_company_id].currency
                res[account_id] += currency_obj.compute(from_currency,
                        account_sum.get(child_id, Decimal('0.0')), to_currency,
                        round=True)

        youngest_fiscalyear = None
        for fiscalyear in fiscalyear_obj.browse(fiscalyear_ids):
            if not youngest_fiscalyear \
                    or youngest_fiscalyear.start_date > fiscalyear.start_date:
                youngest_fiscalyear = fiscalyear

        fiscalyear = None
        if youngest_fiscalyear:
            fiscalyear_ids = fiscalyear_obj.search([
                ('end_date', '<=', youngest_fiscalyear.start_date),
                ('company', '=', youngest_fiscalyear.company),
                ], order=[('end_date', 'DESC')], limit=1)
            if fiscalyear_ids:
                fiscalyear = fiscalyear_obj.browse(fiscalyear_ids[0])

        if fiscalyear:
            if fiscalyear.state == 'close':
                deferral_ids = deferral_obj.search([
                    ('fiscalyear', '=', fiscalyear.id),
                    ('account', 'in', ids),
                    ])
                id2deferral = {}
                for deferral in deferral_obj.browse(deferral_ids):
                    id2deferral[deferral.account.id] = deferral

                for account_id in ids:
                    if account_id in id2deferral:
                        deferral = id2deferral[account_id]
                        res[account_id] += deferral.debit - deferral.credit
            else:
                with Transaction().set_context(fiscalyear=fiscalyear.id,
                        date=False):
                    res2 = self.get_balance(ids, name)
                for account_id in ids:
                    res[account_id] += res2[account_id]

        for account_id in ids:
            company_id = account2company[account_id]
            to_currency = id2company[company_id].currency
            res[account_id] = currency_obj.round(to_currency, res[account_id])
        return res

    def get_credit_debit(self, ids, names):
        '''
        Function to compute debit, credit for account ids.

        :param ids: the ids of the account
        :param names: the list of field name to compute
        :return: a dictionary with all field names as key and
            a dictionary as value with id as key
        '''
        res = {}
        pool = Pool()
        move_line_obj = pool.get('account.move.line')
        company_obj = pool.get('company.company')
        currency_obj = pool.get('currency.currency')
        fiscalyear_obj = pool.get('account.fiscalyear')
        deferral_obj = pool.get('account.account.deferral')
        cursor = Transaction().cursor

        for name in names:
            if name not in ('credit', 'debit'):
                raise Exception('Bad argument')
            res[name] = {}

        line_query, fiscalyear_ids = move_line_obj.query_get()
        for i in range(0, len(ids), cursor.IN_MAX):
            sub_ids = ids[i:i + cursor.IN_MAX]
            red_sql, red_ids = reduce_ids('a.id', sub_ids)
            cursor.execute('SELECT a.id, ' + \
                        ','.join('SUM(COALESCE(l.' + name + ', 0))'
                            for name in names) + ' ' \
                    'FROM account_account a ' \
                        'LEFT JOIN account_move_line l ' \
                        'ON (a.id = l.account) ' \
                    'WHERE a.kind != \'view\' ' \
                        'AND ' + red_sql + ' ' \
                        'AND ' + line_query + ' ' \
                        'AND a.active ' \
                    'GROUP BY a.id', red_ids)
            for row in cursor.fetchall():
                account_id = row[0]
                for i in range(len(names)):
                    # SQLite uses float for SUM
                    if not isinstance(row[i + 1], Decimal):
                        res[names[i]][account_id] = Decimal(str(row[i + 1]))
                    else:
                        res[names[i]][account_id] = row[i + 1]

        account2company = {}
        id2company = {}
        accounts = self.browse(ids)
        for account in accounts:
            account2company[account.id] = account.company.id
            id2company[account.company.id] = account.company

        for account_id in ids:
            for name in names:
                res[name].setdefault(account_id, Decimal('0.0'))

        youngest_fiscalyear = None
        for fiscalyear in fiscalyear_obj.browse(fiscalyear_ids):
            if not youngest_fiscalyear \
                    or youngest_fiscalyear.start_date > fiscalyear.start_date:
                youngest_fiscalyear = fiscalyear

        fiscalyear = None
        if youngest_fiscalyear:
            fiscalyear_ids = fiscalyear_obj.search([
                ('end_date', '<=', youngest_fiscalyear.start_date),
                ('company', '=', youngest_fiscalyear.company),
                ], order=[('end_date', 'DESC')], limit=1)
            if fiscalyear_ids:
                fiscalyear = fiscalyear_obj.browse(fiscalyear_ids[0])

        if fiscalyear:
            if fiscalyear.state == 'close':
                deferral_ids = deferral_obj.search([
                    ('fiscalyear', '=', fiscalyear.id),
                    ('account', 'in', ids),
                    ])
                id2deferral = {}
                for deferral in deferral_obj.browse(deferral_ids):
                    id2deferral[deferral.account.id] = deferral

                for account_id in ids:
                    if account_id in id2deferral:
                        deferral = id2deferral[account_id]
                        for name in names:
                            res[name][account_id] += deferral[name]
            else:
                with Transaction().set_context(fiscalyear=fiscalyear.id,
                        date=False):
                    res2 = self.get_credit_debit(ids, names)
                for account_id in ids:
                    for name in names:
                        res[name][account_id] += res2[name][account_id]

        for account_id in ids:
            company_id = account2company[account_id]
            currency = id2company[company_id].currency
            for name in names:
                res[name][account_id] = currency_obj.round(currency,
                        res[name][account_id])
        return res

    def get_rec_name(self, ids, name):
        if not ids:
            return {}
        res = {}
        for account in self.browse(ids):
            if account.code:
                res[account.id] = account.code + ' - ' + account.name
            else:
                res[account.id] = account.name
        return res

    def search_rec_name(self, name, clause):
        ids = self.search([
            ('code',) + clause[1:],
            ], limit=1)
        if ids:
            return [('code',) + clause[1:]]
        return [(self._rec_name,) + clause[1:]]

    def copy(self, ids, default=None):
        if default is None:
            default = {}
        default['left'] = 0
        default['right'] = 0
        res = super(Account, self).copy(ids, default=default)
        self._rebuild_tree('parent', False, 0)
        return res

    def write(self, ids, vals):
        if not vals.get('active', True):
            move_line_obj = Pool().get('account.move.line')
            account_ids = self.search([
                ('parent', 'child_of', ids),
                ])
            if move_line_obj.search([
                ('account', 'in', account_ids),
                ]):
                vals = vals.copy()
                del vals['active']
        return super(Account, self).write(ids, vals)

    def delete(self, ids):
        move_line_obj = Pool().get('account.move.line')
        if isinstance(ids, (int, long)):
            ids = [ids]
        account_ids = self.search([
            ('parent', 'child_of', ids),
            ])
        if move_line_obj.search([
            ('account', 'in', account_ids),
            ]):
            self.raise_user_error('delete_account_containing_move_lines')
        return super(Account, self).delete(account_ids)

    def update_account(self, account, template2account=None,
            template2type=None):
        '''
        Update recursively accounts based on template.

        :param account: an account id or the BrowseRecord of the account
        :param template2account: a dictionary with template id as key
                and account id as value, used to convert template id
                into account. The dictionary is filled with new accounts
        :param template2type: a dictionary with type template id as key
                and type id as value, used to convert type template id
                into type.
        '''
        template_obj = Pool().get('account.account.template')
        lang_obj = Pool().get('ir.lang')

        if template2account is None:
            template2account = {}

        if template2type is None:
            template2type = {}

        if isinstance(account, (int, long)):
            account = self.browse(account)

        if account.template:
            vals = template_obj._get_account_value(account.template,
                    account=account)
            if account.type.id != template2type.get(account.template.type.id,
                    False):
                vals['type'] = template2type.get(account.template.type.id,
                        False)
            if vals:
                self.write(account.id, vals)

            prev_lang = account._context.get('language') or 'en_US'
            prev_data = {}
            for field_name, field in account.template._columns.iteritems():
                if getattr(field, 'translate', False):
                    prev_data[field_name] = account.template[field_name]
            for lang in lang_obj.get_translatable_languages():
                if lang == prev_lang:
                    continue
                account.setLang(lang)
                data = {}
                for field_name, field in account.template._columns.iteritems():
                    if (getattr(field, 'translate', False)
                            and account.template[field_name] !=
                            prev_data[field_name]):
                        data[field_name] = account.template[field_name]
                if data:
                    with Transaction().set_context(language=lang):
                        self.write(account.id, data)
            account.setLang(prev_lang)
            template2account[account.template.id] = account.id

        for child in account.childs:
            self.update_account(child, template2account=template2account,
                    template2type=template2type)

    def update_account_taxes(self, account, template2account, template2tax):
        '''
        Update recursively account taxes base on template.

        :param account: the account id or the BrowseRecord of account
        :param template2account: a dictionary with template id as key
            and account id as value, used to convert template id into
            account.
        :param template2tax: a dictionary with tax template id as key
            and tax id as value, used to convert tax template id into
            tax.
        '''
        if template2account is None:
            template2account = {}

        if template2tax is None:
            template2tax = {}

        if isinstance(account, (int, long)):
            account = self.browse(account)

        if account.template:
            if account.template.taxes:
                tax_ids = [template2tax[x.id] for x in account.template.taxes
                        if x.id in template2tax]
                old_tax_ids = [x.id for x in account.taxes]
                for tax_id in tax_ids:
                    if tax_id not in old_tax_ids:
                        self.write(account.id, {
                            'taxes': [
                                ('add', template2tax[x.id]) \
                                        for x in account.template.taxes \
                                        if x.id in template2tax],
                            })
                        break

        for child in account.childs:
            self.update_account_taxes(child, template2account, template2tax)

Account()


class AccountDeferral(ModelSQL, ModelView):
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
    debit = fields.Numeric('Debit', digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits'])
    credit = fields.Numeric('Credit', digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits'])
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
            'get_currency_digits')

    def __init__(self):
        super(AccountDeferral, self).__init__()
        self._sql_constraints += [
            ('deferral_uniq', 'UNIQUE(account, fiscalyear)',
                'Deferral must be unique by account and fiscal year'),
        ]
        self._error_messages.update({
            'write_deferral': 'You can not modify Account Deferral records',
            })

    def get_currency_digits(self, ids, name):
        res = {}
        for deferral in self.browse(ids):
            res[deferral.id] = deferral.account.currency_digits
        return res

    def get_rec_name(self, ids, name):
        if not ids:
            return {}
        res = {}
        for deferral in self.browse(ids):
            res[deferral.id] = deferral.account.rec_name + ' - ' + \
                    deferral.fiscalyear.rec_name
        return res

    def search_rec_name(self, name, clause):
        ids = self.search(['OR',
            ('account.rec_name',) + clause[1:],
            ('fiscalyear.rec_name',) + clause[1:],
            ])
        return [('id', 'in', ids)]

    def write(self, ids, vals):
        self.raise_user_error('write_deferral')

AccountDeferral()


class OpenChartAccountInit(ModelView):
    'Open Chart Account Init'
    _name = 'account.account.open_chart_account.init'
    _description = __doc__
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
            help='Leave empty for all open fiscal year')
    posted = fields.Boolean('Posted Move', help='Show only posted move')

    def default_posted(self):
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

    def _action_open_chart(self, data):
        model_data_obj = Pool().get('ir.model.data')
        act_window_obj = Pool().get('ir.action.act_window')
        act_window_id = model_data_obj.get_id('account', 'act_account_tree2')
        res = act_window_obj.read(act_window_id)
        res['pyson_context'] = PYSONEncoder().encode({
            'fiscalyear': data['form']['fiscalyear'],
            'posted': data['form']['posted'],
            })
        return res

OpenChartAccount()


class PrintGeneralLegderInit(ModelView):
    'Print General Ledger'
    _name = 'account.account.print_general_ledger.init'
    _description = __doc__
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
            required=True, on_change=['fiscalyear'])
    start_period = fields.Many2One('account.period', 'Start Period',
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear')),
            ('start_date', '<=', (Eval('end_period'), 'start_date')),
            ], depends=['fiscalyear', 'end_period'])
    end_period = fields.Many2One('account.period', 'End Period',
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear')),
            ('start_date', '>=', (Eval('start_period'), 'start_date'))
            ],
        depends=['fiscalyear', 'start_period'])
    company = fields.Many2One('company.company', 'Company', required=True)
    posted = fields.Boolean('Posted Move', help='Show only posted move')
    empty_account = fields.Boolean('Empty Account',
            help='With account without move')

    def default_fiscalyear(self):
        fiscalyear_obj = Pool().get('account.fiscalyear')
        fiscalyear_id = fiscalyear_obj.find(
                Transaction().context.get('company', False), exception=False)
        if fiscalyear_id:
            return fiscalyear_id
        return False

    def default_company(self):
        return Transaction().context.get('company') or False

    def default_posted(self):
        return False

    def default_empty_account(self):
        return False

    def on_change_fiscalyear(self, vals):
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

    def parse(self, report, objects, datas, localcontext):
        pool = Pool()
        account_obj = pool.get('account.account')
        period_obj = pool.get('account.period')
        company_obj = pool.get('company.company')

        company = company_obj.browse(datas['form']['company'])

        account_ids = account_obj.search([
            ('company', '=', datas['form']['company']),
            ('kind', '!=', 'view'),
            ], order=[('code', 'ASC'), ('id', 'ASC')])

        start_period_ids = [0]
        if datas['form']['start_period']:
            start_period = period_obj.browse(datas['form']['start_period'])
            start_period_ids = period_obj.search([
                ('fiscalyear', '=', datas['form']['fiscalyear']),
                ('end_date', '<=', start_period.start_date),
                ])

        with Transaction().set_context(
                fiscalyear=datas['form']['fiscalyear'],
                periods=start_period_ids,
                posted=datas['form']['posted']):
            start_accounts = account_obj.browse(account_ids)
        id2start_account = {}
        for account in start_accounts:
            id2start_account[account.id] = account

        end_period_ids = []
        if datas['form']['end_period']:
            end_period = period_obj.browse(datas['form']['end_period'])
            end_period_ids = period_obj.search([
                ('fiscalyear', '=', datas['form']['fiscalyear']),
                ('end_date', '<=', end_period.start_date),
                ])
            if datas['form']['end_period'] not in end_period_ids:
                end_period_ids.append(datas['form']['end_period'])
        else:
            end_period_ids = period_obj.search([
                ('fiscalyear', '=', datas['form']['fiscalyear']),
                ])

        with Transaction().set_context(
                fiscalyear=datas['form']['fiscalyear'],
                periods=end_period_ids,
                posted=datas['form']['posted']):
            end_accounts = account_obj.browse(account_ids)
        id2end_account = {}
        for account in end_accounts:
            id2end_account[account.id] = account

        periods = period_obj.browse(end_period_ids)
        periods.sort(lambda x, y: cmp(x.start_date, y.start_date))
        localcontext['start_period'] = periods[0]
        periods.sort(lambda x, y: cmp(x.end_date, y.end_date))
        localcontext['end_period'] = periods[-1]

        if not datas['form']['empty_account']:
            account_id2lines = self.get_lines(account_ids,
                    end_period_ids, datas['form']['posted'])
            for account_id in (set(account_ids) - set(account_id2lines)):
                account_ids.remove(account_id)
            account_id2lines = None

        account_id2lines = self.lines(account_ids,
                list(set(end_period_ids).difference(set(start_period_ids))),
                datas['form']['posted'])

        localcontext['accounts'] = account_obj.browse(account_ids)
        localcontext['id2start_account'] = id2start_account
        localcontext['id2end_account'] = id2end_account
        localcontext['digits'] = company.currency.digits
        localcontext['lines'] = lambda account_id: account_id2lines[account_id]
        localcontext['company'] = company

        return super(GeneralLegder, self).parse(report, objects, datas,
                localcontext)

    def get_lines(self, account_ids, period_ids, posted):
        move_line_obj = Pool().get('account.move.line')
        clause = [
            ('account', 'in', account_ids),
            ('period', 'in', period_ids),
            ('state', '!=', 'draft'),
            ]
        if posted:
            clause.append(('move.state', '=', 'posted'))
        move_ids = move_line_obj.search(clause, order=[])
        res = {}
        for move in move_line_obj.browse(move_ids):
            res.setdefault(move.account.id, []).append(move)
        return res

    def lines(self, account_ids, period_ids, posted):
        move_line_obj = Pool().get('account.move.line')
        move_obj = Pool().get('account.move')
        res = dict((account_id, []) for account_id in account_ids)
        account_id2lines = self.get_lines(account_ids, period_ids, posted)

        state_selections = dict(move_obj.fields_get(
            fields_names=['state'])['state']['selection'])

        for account_id, lines in account_id2lines.iteritems():
            lines.sort(lambda x, y: cmp(x.date, y.date))
            balance = Decimal('0.0')
            for line in lines:
                balance += line.debit - line.credit
                res[account_id].append({
                    'date': line.date,
                    'debit': line.debit,
                    'credit': line.credit,
                    'balance': balance,
                    'name': line.name,
                    'state': state_selections.get(line.move.state, line.move.state),
                    })
        return res

GeneralLegder()


class PrintTrialBalanceInit(ModelView):
    'Print Trial Balance Init'
    _name = 'account.account.print_trial_balance.init'
    _description = __doc__
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
            required=True, on_change=['fiscalyear'],
            depends=['start_period', 'end_period'])
    start_period = fields.Many2One('account.period', 'Start Period',
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear')),
            ('start_date', '<=', (Eval('end_period'), 'start_date'))
            ],
        depends=['end_period', 'fiscalyear'])
    end_period = fields.Many2One('account.period', 'End Period',
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear')),
            ('start_date', '>=', (Eval('start_period'), 'start_date'))
            ],
        depends=['start_period', 'fiscalyear'])
    company = fields.Many2One('company.company', 'Company', required=True)
    posted = fields.Boolean('Posted Move', help='Show only posted move')
    empty_account = fields.Boolean('Empty Account',
            help='With account without move')

    def default_fiscalyear(self):
        fiscalyear_obj = Pool().get('account.fiscalyear')
        fiscalyear_id = fiscalyear_obj.find(
                Transaction().context.get('company') or False, exception=False)
        if fiscalyear_id:
            return fiscalyear_id
        return False

    def default_company(self):
        return Transaction().context.get('company') or False

    def default_posted(self):
        return False

    def default_empty_account(self):
        return False

    def on_change_fiscalyear(self, vals):
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

    def parse(self, report, objects, datas, localcontext):
        pool = Pool()
        account_obj = pool.get('account.account')
        period_obj = pool.get('account.period')
        company_obj = pool.get('company.company')

        company = company_obj.browse(datas['form']['company'])

        account_ids = account_obj.search([
            ('company', '=', datas['form']['company']),
            ('kind', '!=', 'view'),
            ])

        start_period_ids = [0]
        if datas['form']['start_period']:
            start_period = period_obj.browse(datas['form']['start_period'])
            start_period_ids = period_obj.search([
                ('fiscalyear', '=', datas['form']['fiscalyear']),
                ('end_date', '<=', start_period.start_date),
                ])

        end_period_ids = []
        if datas['form']['end_period']:
            end_period = period_obj.browse(datas['form']['end_period'])
            end_period_ids = period_obj.search([
                ('fiscalyear', '=', datas['form']['fiscalyear']),
                ('end_date', '<=', end_period.start_date),
                ])
            end_period_ids = list(set(end_period_ids).difference(
                set(start_period_ids)))
            if datas['form']['end_period'] not in end_period_ids:
                end_period_ids.append(datas['form']['end_period'])
        else:
            end_period_ids = period_obj.search([
                ('fiscalyear', '=', datas['form']['fiscalyear']),
                ])
            end_period_ids = list(set(end_period_ids).difference(
                set(start_period_ids)))

        with Transaction().set_context(
                fiscalyear=datas['form']['fiscalyear'],
                periods=end_period_ids,
                posted=datas['form']['posted']):
            accounts = account_obj.browse(account_ids)

        if not datas['form']['empty_account']:
            to_remove = []
            for account in accounts:
                if account.debit == Decimal('0.0') \
                        and account.credit == Decimal('0.0'):
                    to_remove.append(account)
            for account in to_remove:
                accounts.remove(account)

        periods = period_obj.browse(end_period_ids)

        localcontext['accounts'] = accounts
        periods.sort(key=operator.attrgetter('start_date'))
        localcontext['start_period'] = periods[0]
        periods.sort(key=operator.attrgetter('end_date'))
        localcontext['end_period'] = periods[-1]
        localcontext['company'] = company
        localcontext['digits'] = company.currency.digits
        localcontext['sum'] = lambda accounts, field: self.sum(accounts, field)

        return super(TrialBalance, self).parse(report, objects, datas,
                localcontext)

    def sum(self, accounts, field):
        amount = Decimal('0.0')
        for account in accounts:
            amount += account[field]
        return amount

TrialBalance()


class OpenBalanceSheetInit(ModelView):
    'Open Balance Sheet Init'
    _name = 'account.account.open_balance_sheet.init'
    _description = __doc__
    date = fields.Date('Date', required=True)
    company = fields.Many2One('company.company', 'Company', required=True)
    posted = fields.Boolean('Posted Move', help='Show only posted move')

    def default_date(self):
        date_obj = Pool().get('ir.date')
        return date_obj.today()

    def default_company(self):
        return Transaction().context.get('company') or False

    def default_posted(self):
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

    def _action_open(self, datas):
        pool = Pool()
        model_data_obj = pool.get('ir.model.data')
        act_window_obj = pool.get('ir.action.act_window')
        company_obj = pool.get('company.company')
        lang_obj = pool.get('ir.lang')

        company = company_obj.browse(datas['form']['company'])
        for code in [Transaction().language, 'en_US']:
            lang_ids = lang_obj.search([
                ('code', '=', code),
                ])
            if lang_ids:
                break
        lang = lang_obj.browse(lang_ids[0])

        date = lang_obj.strftime(datas['form']['date'], lang.code, lang.date)

        act_window_id = model_data_obj.get_id('account',
                'act_account_balance_sheet_tree')
        res = act_window_obj.read(act_window_id)
        res['pyson_context'] = PYSONEncoder().encode({
            'date': Date(datas['form']['date'].year,
                datas['form']['date'].month,
                datas['form']['date'].day),
            'posted': datas['form']['posted'],
            'company': datas['form']['company'],
            })
        res['name'] = res['name'] + ' - '+ date + ' - ' + company.name
        return res

OpenBalanceSheet()


class OpenIncomeStatementInit(ModelView):
    'Open Income Statement Init'
    _name = 'account.account.open_income_statement.init'
    _description = __doc__
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
            required=True, on_change=['fiscalyear'],
            depends=['start_period', 'end_period'])
    start_period = fields.Many2One('account.period', 'Start Period',
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear')),
            ('start_date', '<=', (Eval('end_period'), 'start_date'))
            ],
        depends=['end_period', 'fiscalyear'])
    end_period = fields.Many2One('account.period', 'End Period',
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear')),
            ('start_date', '>=', (Eval('start_period'), 'start_date')),
            ],
        depends=['start_period', 'fiscalyear'])
    company = fields.Many2One('company.company', 'Company', required=True)
    posted = fields.Boolean('Posted Move', help='Show only posted move')

    def default_fiscalyear(self):
        fiscalyear_obj = Pool().get('account.fiscalyear')
        fiscalyear_id = fiscalyear_obj.find(
                Transaction().context.get('company') or False, exception=False)
        if fiscalyear_id:
            return fiscalyear_id
        return False

    def default_company(self):
        return Transaction().context.get('company') or False

    def default_posted(self):
        return False

    def on_change_fiscalyear(self, vals):
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

    def _action_open(self, datas):
        pool = Pool()
        model_data_obj = pool.get('ir.model.data')
        act_window_obj = pool.get('ir.action.act_window')
        period_obj = pool.get('account.period')

        start_period_ids = [0]
        if datas['form']['start_period']:
            start_period = period_obj.browse(datas['form']['start_period'])
            start_period_ids = period_obj.search([
                ('fiscalyear', '=', datas['form']['fiscalyear']),
                ('end_date', '<=', start_period.start_date),
                ])

        end_period_ids = []
        if datas['form']['end_period']:
            end_period = period_obj.browse(datas['form']['end_period'])
            end_period_ids = period_obj.search([
                ('fiscalyear', '=', datas['form']['fiscalyear']),
                ('end_date', '<=', end_period.start_date),
                ])
            end_period_ids = list(set(end_period_ids).difference(
                set(start_period_ids)))
            if datas['form']['end_period'] not in end_period_ids:
                end_period_ids.append(datas['form']['end_period'])
        else:
            end_period_ids = period_obj.search([
                ('fiscalyear', '=', datas['form']['fiscalyear']),
                ])
            end_period_ids = list(set(end_period_ids).difference(
                set(start_period_ids)))

        act_window_id = model_data_obj.get_id('account',
                'act_account_income_statement_tree')
        res = act_window_obj.read(act_window_id)
        res['pyson_context'] = PYSONEncoder().encode({
            'periods': end_period_ids,
            'posted': datas['form']['posted'],
            'company': datas['form']['company'],
            })
        return res

OpenIncomeStatement()


class CreateChartAccountInit(ModelView):
    'Create Chart Account Init'
    _name = 'account.account.create_chart_account.init'
    _description = __doc__

CreateChartAccountInit()


class CreateChartAccountAccount(ModelView):
    'Create Chart Account Account'
    _name = 'account.account.create_chart_account.account'
    _description = __doc__
    company = fields.Many2One('company.company', 'Company', required=True)
    account_template = fields.Many2One('account.account.template',
            'Account Template', required=True, domain=[('parent', '=', False)])

    def default_company(self):
        return Transaction().context.get('company') or False

CreateChartAccountAccount()


class CreateChartAccountPropertites(ModelView):
    'Create Chart Account Properties'
    _name = 'account.account.create_chart_account.properties'
    _description = __doc__
    company = fields.Many2One('company.company', 'Company')
    account_receivable = fields.Many2One('account.account',
            'Default Receivable Account',
            domain=[
                ('kind', '=', 'receivable'),
                ('company', '=', Eval('company')),
            ],
            depends=['company'])
    account_payable = fields.Many2One('account.account',
            'Default Payable Account',
            domain=[
                ('kind', '=', 'payable'),
                ('company', '=', Eval('company')),
            ],
            depends=['company'])

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

    def _action_create_account(self, datas):
        pool = Pool()
        account_type_template_obj = \
                pool.get('account.account.type.template')
        account_template_obj = pool.get('account.account.template')
        tax_code_template_obj = pool.get('account.tax.code.template')
        tax_template_obj = pool.get('account.tax.template')
        tax_rule_template_obj = pool.get('account.tax.rule.template')
        tax_rule_line_template_obj = \
                pool.get('account.tax.rule.line.template')

        with Transaction().set_context(language='en_US'):
            account_template = account_template_obj.browse(
                    datas['form']['account_template'])

            # Create account types
            template2type = {}
            account_type_template_obj.create_type(account_template.type,
                    datas['form']['company'], template2type=template2type)

            # Create accounts
            template2account = {}
            account_template_obj.create_account(account_template,
                    datas['form']['company'],
                    template2account=template2account,
                    template2type=template2type)

            # Create tax codes
            template2tax_code = {}
            tax_code_template_ids = tax_code_template_obj.search([
                ('account', '=', datas['form']['account_template']),
                ('parent', '=', False),
                ])
            for tax_code_template in tax_code_template_obj.browse(
                    tax_code_template_ids):
                tax_code_template_obj.create_tax_code(tax_code_template,
                        datas['form']['company'],
                        template2tax_code=template2tax_code)

            # Create taxes
            template2tax = {}
            tax_template_ids = tax_template_obj.search([
                ('account', '=', datas['form']['account_template']),
                ('parent', '=', False),
                ])
            for tax_template in tax_template_obj.browse(tax_template_ids):
                tax_template_obj.create_tax(tax_template,
                        datas['form']['company'],
                        template2tax_code=template2tax_code,
                        template2account=template2account,
                        template2tax=template2tax)

            # Update taxes on accounts
            account_template_obj.update_account_taxes(account_template,
                    template2account, template2tax)

            # Create tax rules
            template2rule = {}
            tax_rule_template_ids = tax_rule_template_obj.search([
                ('account', '=', datas['form']['account_template']),
                ])
            for tax_rule_template in tax_rule_template_obj.browse(
                    tax_rule_template_ids):
                tax_rule_template_obj.create_rule(tax_rule_template,
                        datas['form']['company'], template2rule=template2rule)

            # Create tax rule lines
            template2rule_line = {}
            tax_rule_line_template_ids = tax_rule_line_template_obj.search([
                ('rule.account', '=', datas['form']['account_template']),
                ])
            for tax_rule_line_template in tax_rule_line_template_obj.browse(
                    tax_rule_line_template_ids):
                tax_rule_line_template_obj.create_rule_line(
                        tax_rule_line_template, template2tax, template2rule,
                        template2rule_line=template2rule_line)

        return {'company': datas['form']['company']}

    def _action_create_properties(self, datas):
        property_obj = Pool().get('ir.property')
        model_field_obj = Pool().get('ir.model.field')

        account_receivable_field_id = model_field_obj.search([
            ('model.model', '=', 'party.party'),
            ('name', '=', 'account_receivable'),
            ], limit=1)[0]
        property_ids = property_obj.search([
            ('field', '=', account_receivable_field_id),
            ('res', '=', False),
            ('company', '=', datas['form']['company']),
            ])
        with Transaction().set_user(0):
            property_obj.delete(property_ids)
            if datas['form']['account_receivable']:
                property_obj.create({
                    'name': 'account_receivable',
                    'field': account_receivable_field_id,
                    'value': 'account.account,' + \
                            str(datas['form']['account_receivable']),
                    'company': datas['form']['company'],
                    })

        account_payable_field_id = model_field_obj.search([
            ('model.model', '=', 'party.party'),
            ('name', '=', 'account_payable'),
            ], limit=1)[0]
        property_ids = property_obj.search([
            ('field', '=', account_payable_field_id),
            ('res', '=', False),
            ('company', '=', datas['form']['company']),
            ])
        with Transaction().set_user(0):
            property_obj.delete(property_ids)
            if datas['form']['account_payable']:
                property_obj.create({
                    'name': 'account_payable',
                    'field': account_payable_field_id,
                    'value': 'account.account,' + \
                            str(datas['form']['account_payable']),
                    'company': datas['form']['company'],
                    })
        return {}

CreateChartAccount()


class UpdateChartAccountInit(ModelView):
    'Update Chart Account from Template Init'
    _name = 'account.account.update_chart_account.init'
    _description = __doc__
    account = fields.Many2One('account.account', 'Root Account',
            required=True, domain=[('parent', '=', False)])

UpdateChartAccountInit()


class UpdateChartAccountStart(ModelView):
    'Update Chart Account from Template Start'
    _name = 'account.account.update_chart_account.start'
    _description = __doc__

UpdateChartAccountStart()


class UpdateChartAccount(Wizard):
    'Update Chart Account from Template'
    _name = 'account.account.update_chart_account'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'account.account.update_chart_account.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('start', 'Ok', 'tryton-ok', True),
                ],
            },
        },
        'start': {
            'actions': ['_action_update_account'],
            'result': {
                'type': 'form',
                'object': 'account.account.update_chart_account.start',
                'state': [
                    ('end', 'Ok', 'tryton-ok', True),
                ],
            },
        },
    }

    def _action_update_account(self, datas):
        pool = Pool()
        account_type_obj = pool.get('account.account.type')
        account_type_template_obj = \
                pool.get('account.account.type.template')
        account_obj = pool.get('account.account')
        account_template_obj = pool.get('account.account.template')
        tax_code_obj = pool.get('account.tax.code')
        tax_code_template_obj = pool.get('account.tax.code.template')
        tax_obj = pool.get('account.tax')
        tax_template_obj = pool.get('account.tax.template')
        tax_rule_obj = pool.get('account.tax.rule')
        tax_rule_template_obj = pool.get('account.tax.rule.template')
        tax_rule_line_obj = pool.get('account.tax.rule.line')
        tax_rule_line_template_obj = \
                pool.get('account.tax.rule.line.template')

        account = account_obj.browse(datas['form']['account'])

        # Update account types
        template2type = {}
        account_type_obj.update_type(account.type, template2type=template2type)
        # Create missing account types
        if account.type.template:
            account_type_template_obj.create_type(account.type.template,
                    account.company.id, template2type=template2type)

        # Update accounts
        template2account = {}
        account_obj.update_account(account, template2account=template2account,
                template2type=template2type)
        # Create missing accounts
        if account.template:
            account_template_obj.create_account(account.template,
                    account.company.id, template2account=template2account,
                    template2type=template2type)

        # Update tax codes
        template2tax_code = {}
        tax_code_ids = tax_code_obj.search([
            ('company', '=', account.company.id),
            ('parent', '=', False),
            ])
        for tax_code in tax_code_obj.browse(tax_code_ids):
            tax_code_obj.update_tax_code(tax_code,
                    template2tax_code=template2tax_code)
        # Create missing tax codes
        if account.template:
            tax_code_template_ids = tax_code_template_obj.search([
                ('account', '=', account.template.id),
                ('parent', '=', False),
                ])
            for tax_code_template in tax_code_template_obj.browse(
                    tax_code_template_ids):
                tax_code_template_obj.create_tax_code(tax_code_template,
                        account.company.id,
                        template2tax_code=template2tax_code)

        # Update taxes
        template2tax = {}
        tax_ids = tax_obj.search([
            ('company', '=', account.company.id),
            ('parent', '=', False),
            ])
        for tax in tax_obj.browse(tax_ids):
            tax_obj.update_tax(tax, template2tax_code=template2tax_code,
                    template2account=template2account,
                    template2tax=template2tax)
        # Create missing taxes
        if account.template:
            tax_template_ids = tax_template_obj.search([
                ('account', '=', account.template.id),
                ('parent', '=', False),
                ])
            for tax_template in tax_template_obj.browse(tax_template_ids):
                tax_template_obj.create_tax(tax_template, account.company.id,
                        template2tax_code=template2tax_code,
                        template2account=template2account,
                        template2tax=template2tax)

        # Update taxes on accounts
        account_obj.update_account_taxes(account, template2account,
                template2tax)

        # Update tax rules
        template2rule = {}
        tax_rule_ids = tax_rule_obj.search([
            ('company', '=', account.company.id),
            ])
        for tax_rule in tax_rule_obj.browse(tax_rule_ids):
            tax_rule_obj.update_rule(tax_rule, template2rule=template2rule)
        # Create missing tax rules
        if account.template:
            tax_rule_template_ids = tax_rule_template_obj.search([
                ('account', '=', account.template.id),
                ])
            for tax_rule_template in tax_rule_template_obj.browse(
                    tax_rule_template_ids):
                tax_rule_template_obj.create_rule(tax_rule_template,
                        account.company.id, template2rule=template2rule)

        # Update tax rule lines
        template2rule_line = {}
        tax_rule_line_ids = tax_rule_line_obj.search([
            ('rule.company', '=', account.company.id),
            ])
        for tax_rule_line in tax_rule_line_obj.browse(tax_rule_line_ids):
            tax_rule_line_obj.update_rule_line(tax_rule_line, template2tax,
                    template2rule, template2rule_line=template2rule_line)
        # Create missing tax rule lines
        if account.template:
            tax_rule_line_template_ids = tax_rule_line_template_obj.search([
                ('rule.account', '=', account.template.id),
                ])
            for tax_rule_line_template in tax_rule_line_template_obj.browse(
                    tax_rule_line_template_ids):
                tax_rule_line_template_obj.create_rule_line(
                        tax_rule_line_template, template2tax, template2rule,
                        template2rule_line=template2rule_line)
        return {}

UpdateChartAccount()


class OpenThirdPartyBalanceInit(ModelView):
    'Open Third Party Balance Init'
    _name = 'account.account.open_third_party_balance.init'
    _description = __doc__
    company = fields.Many2One('company.company', 'Company', required=True)
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
            required=True)
    posted = fields.Boolean('Posted Move', help='Show only posted move')


    def default_fiscalyear(self):
        fiscalyear_obj = Pool().get('account.fiscalyear')
        fiscalyear_id = fiscalyear_obj.find(
                Transaction().context.get('company') or False, exception=False)
        if fiscalyear_id:
            return fiscalyear_id
        return False

    def default_posted(self):
        return False

    def default_company(self):
        return Transaction().context.get('company') or False

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

    def parse(self, report, objects, datas, localcontext):
        pool = Pool()
        party_obj = pool.get('party.party')
        move_line_obj = pool.get('account.move.line')
        company_obj = pool.get('company.company')
        date_obj = pool.get('ir.date')
        cursor = Transaction().cursor

        company = company_obj.browse(datas['form']['company'])
        localcontext['company'] = company
        localcontext['digits'] = company.currency.digits
        localcontext['fiscalyear'] = datas['form']['fiscalyear']
        with Transaction().set_context(context=localcontext):
            line_query, _ = move_line_obj.query_get()
        if datas['form']['posted']:
            posted_clause = "AND m.state = 'posted' "
        else:
            posted_clause = ""

        cursor.execute('SELECT l.party, SUM(l.debit), SUM(l.credit) ' \
                'FROM account_move_line l ' \
                    'JOIN account_move m ON (l.move = m.id) '
                    'JOIN account_account a ON (l.account = a.id) '
                'WHERE l.party IS NOT NULL '\
                    'AND a.active ' \
                    'AND a.kind IN (\'payable\',\'receivable\') ' \
                    'AND l.reconciliation IS NULL ' \
                    'AND a.company = %s ' \
                    'AND (l.maturity_date <= %s ' \
                        'OR l.maturity_date IS NULL) '\
                    'AND ' + line_query + ' ' \
                    + posted_clause + \
                'GROUP BY l.party ' \
                'HAVING (SUM(l.debit) != 0 OR SUM(l.credit) != 0)',
                (datas['form']['company'], date_obj.today()))

        res = cursor.fetchall()
        id2party = {}
        for party in party_obj.browse([x[0] for x in res]):
            id2party[party.id] = party
        objects = [{
            'name': id2party[x[0]].rec_name,
            'debit': x[1],
            'credit': x[2],
            'solde': x[1] - x[2],
            } for x in res]
        objects.sort(lambda x, y: cmp(x['name'], y['name']))
        localcontext['total_debit'] = sum((x['debit'] for x in objects))
        localcontext['total_credit'] = sum((x['credit'] for x in objects))
        localcontext['total_solde'] = sum((x['solde'] for x in objects))

        return super(ThirdPartyBalance, self).parse(report, objects, datas,
                localcontext)

ThirdPartyBalance()


class OpenAgedBalanceInit(ModelView):
    'Open Aged Balance Init'
    _name = 'account.account.open_aged_balance.init'
    _description = __doc__
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
    posted = fields.Boolean('Posted Move', help='Show only posted move')

    def default_fiscalyear(self):
        fiscalyear_obj = Pool().get('account.fiscalyear')
        fiscalyear_id = fiscalyear_obj.find(
                Transaction().context.get('company') or False, exception=False)
        if fiscalyear_id:
            return fiscalyear_id
        return False

    def default_balance_type(self):
        return "customer"

    def default_posted(self):
        return False

    def default_term1(self):
        return 30

    def default_term2(self):
        return 60

    def default_term3(self):
        return 90

    def default_unit(self):
        return 'day'

    def default_company(self):
        return Transaction().context.get('company') or False

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

    def check(self, datas):
        if not (datas['form']['term1'] < datas['form']['term2'] \
                  < datas['form']['term3']):
            self.raise_user_error(error="warning",
                    error_description="term_overlap_desc")
        return datas['form']

OpenAgedBalance()


class AgedBalance(Report):
    _name = 'account.account.aged_balance'

    def parse(self, report, objects, datas, localcontext):
        pool = Pool()
        party_obj = pool.get('party.party')
        move_line_obj = pool.get('account.move.line')
        company_obj = pool.get('company.company')
        date_obj = pool.get('ir.date')
        cursor = Transaction().cursor

        company = company_obj.browse(datas['form']['company'])
        localcontext['digits'] = company.currency.digits
        localcontext['fiscalyear'] = datas['form']['fiscalyear']
        localcontext['posted'] = datas['form']['posted']
        with Transaction().set_context(context=localcontext):
            line_query, _ = move_line_obj.query_get()

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
                term_args = (date_obj.today() +
                        datetime.timedelta(days=term*coef),)
            else:
                term_query = '(l.maturity_date <= %s '\
                    'AND l.maturity_date > %s) '
                term_args = (
                    date_obj.today() + datetime.timedelta(days=term*coef),
                    date_obj.today()
                    + datetime.timedelta(days=terms[position-1]*coef),
                    )

            cursor.execute('SELECT l.party, SUM(l.debit) - SUM(l.credit) ' \
                    'FROM account_move_line l ' \
                        'JOIN account_move m ON (l.move = m.id) '
                        'JOIN account_account a ON (l.account = a.id) '
                    'WHERE l.party IS NOT NULL '\
                        'AND a.active ' \
                        'AND a.kind IN ('+ ','.join(('%s',) * len(kind)) + ") "\
                        'AND l.reconciliation IS NULL ' \
                        'AND a.company = %s ' \
                        'AND '+ term_query+\
                        'AND ' + line_query + ' ' \
                    'GROUP BY l.party ' \
                    'HAVING (SUM(l.debit) - SUM(l.credit) != 0)',
                    kind + (datas['form']['company'],) + term_args)
            for party, solde in cursor.fetchall():
                if party in res:
                    res[party][position] = solde
                else:
                    res[party] = [(i[0] == position) and solde \
                            or Decimal("0.0") for i in enumerate(terms)]
        party_ids = party_obj.search([
            ('id', 'in', [k for k in res.iterkeys()]),
            ])
        parties = party_obj.browse(party_ids)

        localcontext['main_title'] = datas['form']['balance_type']
        localcontext['unit'] = datas['form']['unit']
        for i in range(3):
            localcontext['total' + str(i)] = sum((v[i] for v in res.itervalues()))
            localcontext['term' + str(i)] = terms[i]

        localcontext['company'] = company
        localcontext['parties']= [{
            'name': p.rec_name,
            'amount0': res[p.id][0],
            'amount1': res[p.id][1],
            'amount2': res[p.id][2],
            } for p in parties]

        return super(AgedBalance, self).parse(report, objects, datas,
                localcontext)

AgedBalance()
