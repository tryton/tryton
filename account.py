#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
import datetime
import operator
from itertools import izip
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateView, StateAction, StateTransition, \
    Button
from trytond.report import Report
from trytond.tools import reduce_ids
from trytond.pyson import Eval, PYSONEncoder, Date
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.backend import TableHandler

__all__ = ['TypeTemplate', 'Type', 'OpenType', 'AccountTemplate', 'Account',
    'AccountDeferral', 'OpenChartAccountStart', 'OpenChartAccount',
    'PrintGeneralLedgerStart', 'PrintGeneralLedger', 'GeneralLedger',
    'PrintTrialBalanceStart', 'PrintTrialBalance', 'TrialBalance',
    'OpenBalanceSheetStart', 'OpenBalanceSheet',
    'OpenIncomeStatementStart', 'OpenIncomeStatement',
    'CreateChartStart', 'CreateChartAccount', 'CreateChartProperties',
    'CreateChart', 'UpdateChartStart', 'UpdateChartSucceed', 'UpdateChart',
    'OpenThirdPartyBalanceStart', 'OpenThirdPartyBalance', 'ThirdPartyBalance',
    'OpenAgedBalanceStart', 'OpenAgedBalance', 'AgedBalance']


class TypeTemplate(ModelSQL, ModelView):
    'Account Type Template'
    __name__ = 'account.account.type.template'
    name = fields.Char('Name', required=True, translate=True)
    parent = fields.Many2One('account.account.type.template', 'Parent',
            ondelete="RESTRICT")
    childs = fields.One2Many('account.account.type.template', 'parent',
        'Children')
    sequence = fields.Integer('Sequence',
        order_field='(%(table)s.sequence IS NULL) %(order)s, '
        '%(table)s.sequence %(order)s')
    balance_sheet = fields.Boolean('Balance Sheet')
    income_statement = fields.Boolean('Income Statement')
    display_balance = fields.Selection([
        ('debit-credit', 'Debit - Credit'),
        ('credit-debit', 'Credit - Debit'),
        ], 'Display Balance', required=True)

    @classmethod
    def __setup__(cls):
        super(TypeTemplate, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)

        super(TypeTemplate, cls).__register__(module_name)

        # Migration from 2.4: drop required on sequence
        table.not_null_action('sequence', action='remove')

    @classmethod
    def validate(cls, records):
        super(TypeTemplate, cls).validate(records)
        cls.check_recursion(records, rec_name='name')

    @staticmethod
    def default_balance_sheet():
        return False

    @staticmethod
    def default_income_statement():
        return False

    @staticmethod
    def default_display_balance():
        return 'debit-credit'

    def get_rec_name(self, name):
        if self.parent:
            return self.parent.get_rec_name(name) + '\\' + self.name
        else:
            return self.name

    def _get_type_value(self, type=None):
        '''
        Set the values for account creation.
        '''
        res = {}
        if not type or type.name != self.name:
            res['name'] = self.name
        if not type or type.sequence != self.sequence:
            res['sequence'] = self.sequence
        if not type or type.balance_sheet != self.balance_sheet:
            res['balance_sheet'] = self.balance_sheet
        if not type or type.income_statement != self.income_statement:
            res['income_statement'] = self.income_statement
        if not type or type.display_balance != self.display_balance:
            res['display_balance'] = self.display_balance
        if not type or type.template != self:
            res['template'] = self.id
        return res

    def create_type(self, company_id, template2type=None, parent_id=None):
        '''
        Create recursively types based on template.
        template2type is a dictionary with template id as key and type id as
        value, used to convert template id into type. The dictionary is filled
        with new types.
        Return the id of the type created
        '''
        pool = Pool()
        Type = pool.get('account.account.type')
        Lang = pool.get('ir.lang')
        Config = pool.get('ir.configuration')

        if template2type is None:
            template2type = {}

        if self.id not in template2type:
            vals = self._get_type_value()
            vals['company'] = company_id
            vals['parent'] = parent_id

            new_type, = Type.create([vals])

            prev_lang = self._context.get('language') or Config.get_language()
            prev_data = {}
            for field_name, field in self._fields.iteritems():
                if getattr(field, 'translate', False):
                    prev_data[field_name] = getattr(self, field_name)
            for lang in Lang.get_translatable_languages():
                if lang == prev_lang:
                    continue
                with Transaction().set_context(language=lang):
                    template = self.__class__(self.id)
                    data = {}
                    for field_name, field in template._fields.iteritems():
                        if (getattr(field, 'translate', False)
                                and (getattr(template, field_name) !=
                                    prev_data[field_name])):
                            data[field_name] = getattr(template, field_name)
                    if data:
                        Type.write([new_type], data)
            template2type[self.id] = new_type.id
        new_id = template2type[self.id]

        new_childs = []
        for child in self.childs:
            new_childs.append(child.create_type(company_id,
                template2type=template2type, parent_id=new_id))
        return new_id


class Type(ModelSQL, ModelView):
    'Account Type'
    __name__ = 'account.account.type'
    name = fields.Char('Name', size=None, required=True, translate=True)
    parent = fields.Many2One('account.account.type', 'Parent',
        ondelete="RESTRICT", domain=[
            ('company', '=', Eval('company')),
            ], depends=['company'])
    childs = fields.One2Many('account.account.type', 'parent', 'Children',
        domain=[
            ('company', '=', Eval('company')),
        ], depends=['company'])
    sequence = fields.Integer('Sequence',
        order_field='(%(table)s.sequence IS NULL) %(order)s, '
        '%(table)s.sequence %(order)s',
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

    @classmethod
    def __setup__(cls):
        super(Type, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)

        super(Type, cls).__register__(module_name)

        # Migration from 2.4: drop required on sequence
        table.not_null_action('sequence', action='remove')

    @classmethod
    def validate(cls, types):
        super(Type, cls).validate(types)
        cls.check_recursion(types, rec_name='name')

    @staticmethod
    def default_balance_sheet():
        return False

    @staticmethod
    def default_income_statement():
        return False

    @staticmethod
    def default_display_balance():
        return 'debit-credit'

    def get_currency_digits(self, name):
        return self.company.currency.digits

    @classmethod
    def get_amount(cls, types, name):
        pool = Pool()
        Account = pool.get('account.account')

        res = {}
        for type_ in types:
            res[type_.id] = Decimal('0.0')

        childs = cls.search([
                ('parent', 'child_of', [t.id for t in types]),
                ])
        type_sum = {}
        for type_ in childs:
            type_sum[type_.id] = Decimal('0.0')

        accounts = Account.search([
                ('type', 'in', [t.id for t in childs]),
                ])
        for account in accounts:
            type_sum[account.type.id] += account.company.currency.round(
                account.debit - account.credit)

        for type_ in types:
            childs = cls.search([
                    ('parent', 'child_of', [type_.id]),
                    ])
            for child in childs:
                res[type_.id] += type_sum[child.id]
            res[type_.id] = type_.company.currency.round(res[type_.id])
            if type_.display_balance == 'credit-debit':
                res[type_.id] = - res[type_.id]
        return res

    def get_rec_name(self, name):
        if self.parent:
            return self.parent.get_rec_name(name) + '\\' + self.name
        else:
            return self.name

    @classmethod
    def delete(cls, types):
        types = cls.search([
                ('parent', 'child_of', [t.id for t in types]),
                ])
        super(Type, cls).delete(types)

    def update_type(self, template2type=None):
        '''
        Update recursively types based on template.
        template2type is a dictionary with template id as key and type id as
        value, used to convert template id into type. The dictionary is filled
        with new types
        '''
        pool = Pool()
        Lang = pool.get('ir.lang')
        Config = pool.get('ir.configuration')

        if template2type is None:
            template2type = {}

        if self.template:
            vals = self.template._get_type_value(type=self)
            if vals:
                self.write([self], vals)

            prev_lang = self._context.get('language') or Config.get_language()
            prev_data = {}
            for field_name, field in self.template._fields.iteritems():
                if getattr(field, 'translate', False):
                    prev_data[field_name] = getattr(self.template, field_name)
            for lang in Lang.get_translatable_languages():
                if lang == prev_lang:
                    continue
                with Transaction().set_context(language=lang):
                    type_ = self.__class__(self.id)
                    data = {}
                    for field_name, field in (
                            type_.template._fields.iteritems()):
                        if (getattr(field, 'translate', False)
                                and (getattr(type_.template, field_name) !=
                                    prev_data[field_name])):
                            data[field_name] = getattr(type_.template,
                                field_name)
                    if data:
                        self.write([type_], data)
            template2type[self.template.id] = self.id

        for child in self.childs:
            child.update_type(template2type=template2type)


class OpenType(Wizard):
    'Open Type'
    __name__ = 'account.account.open_type'
    start_state = 'open_'
    open_ = StateAction('account.act_account_list2')

    def do_open_(self, action):
        action['pyson_domain'] = PYSONEncoder().encode([
                ('type', '=', Transaction().context['active_id']),
                ])
        action['pyson_context'] = PYSONEncoder().encode({
                'date': Transaction().context.get('date'),
                'posted': Transaction().context.get('posted'),
                })
        return action, {}


class AccountTemplate(ModelSQL, ModelView):
    'Account Template'
    __name__ = 'account.account.template'
    name = fields.Char('Name', size=None, required=True, translate=True,
            select=True)
    code = fields.Char('Code', size=None, select=True)
    type = fields.Many2One('account.account.type.template', 'Type',
        ondelete="RESTRICT",
        states={
            'invisible': Eval('kind') == 'view',
            'required': Eval('kind') != 'view',
            }, depends=['kind'])
    parent = fields.Many2One('account.account.template', 'Parent', select=True,
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
            ('stock', 'Stock'),
            ('view', 'View'),
            ], 'Kind', required=True)
    deferral = fields.Boolean('Deferral', states={
            'invisible': Eval('kind') == 'view',
            }, depends=['kind'])

    @classmethod
    def __setup__(cls):
        super(AccountTemplate, cls).__setup__()
        cls._order.insert(0, ('code', 'ASC'))
        cls._order.insert(1, ('name', 'ASC'))

    @classmethod
    def validate(cls, templates):
        super(AccountTemplate, cls).validate(templates)
        cls.check_recursion(templates)

    @staticmethod
    def default_kind():
        return 'view'

    @staticmethod
    def default_reconcile():
        return False

    @staticmethod
    def default_deferral():
        return True

    def get_rec_name(self, name):
        if self.code:
            return self.code + ' - ' + self.name
        else:
            return self.name

    @classmethod
    def search_rec_name(cls, name, clause):
        templates = cls.search([
                ('code',) + clause[1:],
                ], limit=1)
        if templates:
            return [('code',) + clause[1:]]
        return [(cls._rec_name,) + clause[1:]]

    def _get_account_value(self, account=None):
        '''
        Set the values for account creation.
        '''
        res = {}
        if not account or account.name != self.name:
            res['name'] = self.name
        if not account or account.code != self.code:
            res['code'] = self.code
        if not account or account.kind != self.kind:
            res['kind'] = self.kind
        if not account or account.reconcile != self.reconcile:
            res['reconcile'] = self.reconcile
        if not account or account.deferral != self.deferral:
            res['deferral'] = self.deferral
        if not account or account.template != self:
            res['template'] = self.id
        return res

    def create_account(self, company_id, template2account=None,
            template2type=None, parent_id=None):
        '''
        Create recursively accounts based on template.
        template2account is a dictionary with template id as key and account id
        as value, used to convert template id into account. The dictionary is
        filled with new accounts
        template2type is a dictionary with type template id as key and type id
        as value, used to convert type template id into type.
        Return the id of the account created
        '''
        pool = Pool()
        Account = pool.get('account.account')
        Lang = pool.get('ir.lang')
        Config = pool.get('ir.configuration')

        if template2account is None:
            template2account = {}

        if template2type is None:
            template2type = {}

        if self.id not in template2account:
            vals = self._get_account_value()
            vals['company'] = company_id
            vals['parent'] = parent_id
            vals['type'] = (template2type.get(self.type.id) if self.type
                else None)

            new_account, = Account.create([vals])

            prev_lang = self._context.get('language') or Config.get_language()
            prev_data = {}
            for field_name, field in self._fields.iteritems():
                if getattr(field, 'translate', False):
                    prev_data[field_name] = getattr(self, field_name)
            for lang in Lang.get_translatable_languages():
                if lang == prev_lang:
                    continue
                with Transaction().set_context(language=lang):
                    template = self.__class__(self.id)
                    data = {}
                    for field_name, field in self._fields.iteritems():
                        if (getattr(field, 'translate', False)
                                and (getattr(template, field_name) !=
                                    prev_data[field_name])):
                            data[field_name] = getattr(template, field_name)
                    if data:
                        Account.write([new_account], data)
            template2account[self.id] = new_account.id
        new_id = template2account[self.id]

        new_childs = []
        for child in self.childs:
            new_childs.append(child.create_account(company_id,
                template2account=template2account, template2type=template2type,
                parent_id=new_id))
        return new_id

    def update_account_taxes(self, template2account, template2tax,
            template_done=None):
        '''
        Update recursively account taxes based on template.
        template2account is a dictionary with template id as key and account id
        as value, used to convert template id into account.
        template2tax is a dictionary with tax template id as key and tax id as
        value, used to convert tax template id into tax.
        template_done is a list of template id already updated. The list is
        filled.
        '''
        Account = Pool().get('account.account')

        if template2account is None:
            template2account = {}
        if template2tax is None:
            template2tax = {}
        if template_done is None:
            template_done = []

        if self.id not in template_done:
            if self.taxes:
                Account.write([Account(template2account[self.id])], {
                        'taxes': [
                            ('add', template2tax[x.id]) for x in self.taxes],
                        })
            template_done.append(self.id)

        for child in self.childs:
            child.update_account_taxes(template2account, template2tax,
                template_done=template_done)


class Account(ModelSQL, ModelView):
    'Account'
    __name__ = 'account.account'
    name = fields.Char('Name', size=None, required=True, translate=True,
            select=True)
    code = fields.Char('Code', size=None, select=True)
    active = fields.Boolean('Active', select=True)
    company = fields.Many2One('company.company', 'Company', required=True,
            ondelete="RESTRICT")
    currency = fields.Function(fields.Many2One('currency.currency',
        'Currency'), 'get_currency')
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
            'get_currency_digits')
    second_currency = fields.Many2One('currency.currency',
        'Secondary Currency', help='Force all moves for this account \n'
        'to have this secondary currency.', ondelete="RESTRICT")
    type = fields.Many2One('account.account.type', 'Type', ondelete="RESTRICT",
        states={
            'invisible': Eval('kind') == 'view',
            'required': Eval('kind') != 'view',
            },
        domain=[
            ('company', '=', Eval('company')),
            ], depends=['kind', 'company'])
    parent = fields.Many2One('account.account', 'Parent', select=True,
            left="left", right="right", ondelete="RESTRICT")
    left = fields.Integer('Left', required=True, select=True)
    right = fields.Integer('Right', required=True, select=True)
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
        help='Allow move lines of this account \nto be reconciled.',
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
            ('stock', 'Stock'),
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

    @classmethod
    def __setup__(cls):
        super(Account, cls).__setup__()
        cls._error_messages.update({
                'delete_account_containing_move_lines': ('You can not delete '
                    'account "%s" because it has move lines.'),
                })
        cls._sql_error_messages.update({
                'parent_fkey': ('You can not delete accounts that have '
                    'children.'),
                })
        cls._order.insert(0, ('code', 'ASC'))
        cls._order.insert(1, ('name', 'ASC'))

    @classmethod
    def validate(cls, accounts):
        super(Account, cls).validate(accounts)
        cls.check_recursion(accounts)

    @staticmethod
    def default_left():
        return 0

    @staticmethod
    def default_right():
        return 0

    @staticmethod
    def default_active():
        return True

    @staticmethod
    def default_company():
        return Transaction().context.get('company') or None

    @staticmethod
    def default_reconcile():
        return False

    @staticmethod
    def default_deferral():
        return True

    @staticmethod
    def default_kind():
        return 'view'

    def get_currency(self, name):
        return self.company.currency.id

    def get_currency_digits(self, name):
        return self.company.currency.digits

    @classmethod
    def get_balance(cls, accounts, name):
        res = {}
        pool = Pool()
        Currency = pool.get('currency.currency')
        MoveLine = pool.get('account.move.line')
        FiscalYear = pool.get('account.fiscalyear')
        Deferral = pool.get('account.account.deferral')
        cursor = Transaction().cursor

        query_ids, args_ids = cls.search([
                ('parent', 'child_of', [a.id for a in accounts]),
                ], query_string=True)
        line_query, fiscalyear_ids = MoveLine.query_get()
        cursor.execute('SELECT a.id, '
                    'SUM((COALESCE(l.debit, 0) - COALESCE(l.credit, 0))) '
                'FROM account_account a '
                    'LEFT JOIN account_move_line l '
                    'ON (a.id = l.account) '
                'WHERE a.kind != \'view\' '
                    'AND a.id IN (' + query_ids + ') '
                    'AND ' + line_query + ' '
                    'AND a.active '
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
        all_accounts = cls.search([('parent', 'child_of',
                    [a.id for a in accounts])])
        for account in all_accounts:
            account2company[account.id] = account.company.id
            id2company[account.company.id] = account.company
            id2account[account.id] = account

        for account in accounts:
            res.setdefault(account.id, Decimal('0.0'))
            childs = cls.search([
                    ('parent', 'child_of', [account.id]),
                    ])
            company_id = account2company[account.id]
            to_currency = id2company[company_id].currency
            for child in childs:
                child_company_id = account2company[child.id]
                from_currency = id2company[child_company_id].currency
                res[account.id] += Currency.compute(from_currency,
                        account_sum.get(child.id, Decimal('0.0')), to_currency,
                        round=True)

        youngest_fiscalyear = None
        for fiscalyear in FiscalYear.browse(fiscalyear_ids):
            if not youngest_fiscalyear \
                    or youngest_fiscalyear.start_date > fiscalyear.start_date:
                youngest_fiscalyear = fiscalyear

        fiscalyear = None
        if youngest_fiscalyear:
            fiscalyears = FiscalYear.search([
                ('end_date', '<=', youngest_fiscalyear.start_date),
                ('company', '=', youngest_fiscalyear.company),
                ], order=[('end_date', 'DESC')], limit=1)
            if fiscalyears:
                fiscalyear = fiscalyears[0]

        if fiscalyear:
            if fiscalyear.state == 'close':
                deferrals = Deferral.search([
                    ('fiscalyear', '=', fiscalyear.id),
                    ('account', 'in', [a.id for a in accounts]),
                    ])
                id2deferral = {}
                for deferral in deferrals:
                    id2deferral[deferral.account.id] = deferral

                for account in accounts:
                    if account.id in id2deferral:
                        deferral = id2deferral[account.id]
                        res[account.id] += deferral.debit - deferral.credit
            else:
                with Transaction().set_context(fiscalyear=fiscalyear.id,
                        date=None, periods=None):
                    res2 = cls.get_balance(accounts, name)
                for account in accounts:
                    res[account.id] += res2[account.id]

        for account in accounts:
            company_id = account2company[account.id]
            to_currency = id2company[company_id].currency
            res[account.id] = to_currency.round(res[account.id])
        return res

    @classmethod
    def get_credit_debit(cls, accounts, names):
        '''
        Function to compute debit, credit for accounts.
        If cumulate is set in the context, it is the cumulate amount over all
        previous fiscal year.
        '''
        res = {}
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        FiscalYear = pool.get('account.fiscalyear')
        Deferral = pool.get('account.account.deferral')
        cursor = Transaction().cursor

        for name in names:
            if name not in ('credit', 'debit'):
                raise Exception('Bad argument')
            res[name] = {}

        ids = [a.id for a in accounts]
        line_query, fiscalyear_ids = MoveLine.query_get()
        for i in range(0, len(ids), cursor.IN_MAX):
            sub_ids = ids[i:i + cursor.IN_MAX]
            red_sql, red_ids = reduce_ids('a.id', sub_ids)
            cursor.execute('SELECT a.id, ' +
                        ','.join('SUM(COALESCE(l.' + name + ', 0))'
                            for name in names) + ' '
                    'FROM account_account a '
                        'LEFT JOIN account_move_line l '
                        'ON (a.id = l.account) '
                    'WHERE a.kind != \'view\' '
                        'AND ' + red_sql + ' '
                        'AND ' + line_query + ' '
                        'AND a.active '
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
        for account in accounts:
            account2company[account.id] = account.company.id
            id2company[account.company.id] = account.company

        for account in accounts:
            for name in names:
                res[name].setdefault(account.id, Decimal('0.0'))

        if Transaction().context.get('cumulate'):
            youngest_fiscalyear = None
            for fiscalyear in FiscalYear.browse(fiscalyear_ids):
                if (not youngest_fiscalyear
                        or (youngest_fiscalyear.start_date
                            > fiscalyear.start_date)):
                    youngest_fiscalyear = fiscalyear

            fiscalyear = None
            if youngest_fiscalyear:
                fiscalyears = FiscalYear.search([
                        ('end_date', '<=', youngest_fiscalyear.start_date),
                        ('company', '=', youngest_fiscalyear.company),
                        ], order=[('end_date', 'DESC')], limit=1)
                if fiscalyears:
                    fiscalyear, = fiscalyears

            if fiscalyear:
                if fiscalyear.state == 'close':
                    deferrals = Deferral.search([
                        ('fiscalyear', '=', fiscalyear.id),
                        ('account', 'in', ids),
                        ])
                    id2deferral = {}
                    for deferral in deferrals:
                        id2deferral[deferral.account.id] = deferral

                    for account in accounts:
                        if account.id in id2deferral:
                            deferral = id2deferral[account.id]
                            for name in names:
                                res[name][account.id] += getattr(deferral,
                                    name)
                else:
                    with Transaction().set_context(fiscalyear=fiscalyear.id,
                            date=None, periods=None):
                        res2 = cls.get_credit_debit(accounts, names)
                    for account in accounts:
                        for name in names:
                            res[name][account.id] += res2[name][account.id]

        for account in accounts:
            company_id = account2company[account.id]
            currency = id2company[company_id].currency
            for name in names:
                res[name][account.id] = currency.round(res[name][account.id])
        return res

    def get_rec_name(self, name):
        if self.code:
            return self.code + ' - ' + self.name
        else:
            return self.name

    @classmethod
    def search_rec_name(cls, name, clause):
        accounts = cls.search([
                ('code',) + clause[1:],
                ], limit=1)
        if accounts:
            return [('code',) + clause[1:]]
        return [(cls._rec_name,) + clause[1:]]

    @classmethod
    def copy(cls, accounts, default=None):
        if default is None:
            default = {}
        default['left'] = 0
        default['right'] = 0
        default.setdefault('deferrals', [])
        new_accounts = super(Account, cls).copy(accounts, default=default)
        cls._rebuild_tree('parent', None, 0)
        return new_accounts

    @classmethod
    def write(cls, accounts, vals):
        if not vals.get('active', True):
            MoveLine = Pool().get('account.move.line')
            childs = cls.search([
                    ('parent', 'child_of', [a.id for a in accounts]),
                    ])
            if MoveLine.search([
                        ('account', 'in', [a.id for a in childs]),
                        ]):
                vals = vals.copy()
                del vals['active']
        super(Account, cls).write(accounts, vals)

    @classmethod
    def delete(cls, accounts):
        MoveLine = Pool().get('account.move.line')
        childs = cls.search([
                ('parent', 'child_of', [a.id for a in accounts]),
                ])
        lines = MoveLine.search([
                ('account', 'in', [a.id for a in childs]),
                ])
        if lines:
            cls.raise_user_error('delete_account_containing_move_lines', (
                    lines[0].account.rec_name,))
        super(Account, cls).delete(accounts)

    def update_account(self, template2account=None, template2type=None):
        '''
        Update recursively accounts based on template.
        template2account is a dictionary with template id as key and account id
        as value, used to convert template id into account. The dictionary is
        filled with new accounts.
        template2type is a dictionary with type template id as key and type id
        as value, used to convert type template id into type.
        '''
        pool = Pool()
        Lang = pool.get('ir.lang')
        Config = pool.get('ir.configuration')

        if template2account is None:
            template2account = {}

        if template2type is None:
            template2type = {}

        if self.template:
            vals = self.template._get_account_value(account=self)
            current_type = self.type.id if self.type else None
            template_type = (template2type.get(self.template.type.id)
                if self.template.type else None)
            if current_type != template2type:
                vals['type'] = template_type
            if vals:
                self.write([self], vals)

            prev_lang = self._context.get('language') or Config.get_language()
            prev_data = {}
            for field_name, field in self.template._fields.iteritems():
                if getattr(field, 'translate', False):
                    prev_data[field_name] = getattr(self.template, field_name)
            for lang in Lang.get_translatable_languages():
                if lang == prev_lang:
                    continue
                with Transaction().set_context(language=lang):
                    account = self.__class__(self.id)
                    data = {}
                    for field_name, field in (
                            account.template._fields.iteritems()):
                        if (getattr(field, 'translate', False)
                                and (getattr(account.template, field_name) !=
                                    prev_data[field_name])):
                            data[field_name] = getattr(account.template,
                                field_name)
                    if data:
                        self.write([account], data)
            template2account[self.template.id] = self.id

        for child in self.childs:
            child.update_account(template2account=template2account,
                template2type=template2type)

    def update_account_taxes(self, template2account, template2tax):
        '''
        Update recursively account taxes base on template.
        template2account is a dictionary with template id as key and account id
        as value, used to convert template id into account.
        template2tax is a dictionary with tax template id as key and tax id as
        value, used to convert tax template id into tax.
        '''
        if template2account is None:
            template2account = {}

        if template2tax is None:
            template2tax = {}

        if self.template:
            if self.template.taxes:
                tax_ids = [template2tax[x.id] for x in self.template.taxes
                        if x.id in template2tax]
                old_tax_ids = [x.id for x in self.taxes]
                for tax_id in tax_ids:
                    if tax_id not in old_tax_ids:
                        self.write([self], {
                            'taxes': [
                                    ('add', template2tax[x.id])
                                    for x in self.template.taxes
                                    if x.id in template2tax],
                                })
                        break

        for child in self.childs:
            child.update_account_taxes(template2account, template2tax)


class AccountDeferral(ModelSQL, ModelView):
    '''
    Account Deferral

    It is used to deferral the debit/credit of account by fiscal year.
    '''
    __name__ = 'account.account.deferral'
    account = fields.Many2One('account.account', 'Account', required=True,
            select=True)
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
            required=True, select=True)
    debit = fields.Numeric('Debit', digits=(16, Eval('currency_digits', 2)),
        required=True, depends=['currency_digits'])
    credit = fields.Numeric('Credit', digits=(16, Eval('currency_digits', 2)),
        required=True, depends=['currency_digits'])
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
            'get_currency_digits')

    @classmethod
    def __setup__(cls):
        super(AccountDeferral, cls).__setup__()
        cls._sql_constraints += [
            ('deferral_uniq', 'UNIQUE(account, fiscalyear)',
                'Deferral must be unique by account and fiscal year'),
        ]
        cls._error_messages.update({
            'write_deferral': 'You can not modify Account Deferral records',
            })

    def get_currency_digits(self, name):
        return self.account.currency_digits

    def get_rec_name(self, name):
        return '%s - %s' % (self.account.rec_name, self.fiscalyear.rec_name)

    @classmethod
    def search_rec_name(cls, name, clause):
        deferrals = cls.search(['OR',
                ('account.rec_name',) + clause[1:],
                ('fiscalyear.rec_name',) + clause[1:],
                ])
        return [('id', 'in', [d.id for d in deferrals])]

    @classmethod
    def write(cls, deferrals, vals):
        cls.raise_user_error('write_deferral')


class OpenChartAccountStart(ModelView):
    'Open Chart of Accounts'
    __name__ = 'account.open_chart.start'
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
            help='Leave empty for all open fiscal year')
    posted = fields.Boolean('Posted Move', help='Show only posted move')

    @staticmethod
    def default_posted():
        return False


class OpenChartAccount(Wizard):
    'Open Chart of Accounts'
    __name__ = 'account.open_chart'
    start = StateView('account.open_chart.start',
        'account.open_chart_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Open', 'open_', 'tryton-ok', default=True),
            ])
    open_ = StateAction('account.act_account_tree2')

    def do_open_(self, action):
        action['pyson_context'] = PYSONEncoder().encode({
            'fiscalyear': (self.start.fiscalyear.id
                    if self.start.fiscalyear else None),
            'posted': self.start.posted,
            })
        if self.start.fiscalyear:
            action['name'] += ' - %s' % self.start.fiscalyear.rec_name
        if self.start.posted:
            action['name'] += '*'
        return action, {}

    def transition_open_(self):
        return 'end'


class PrintGeneralLedgerStart(ModelView):
    'Print General Ledger'
    __name__ = 'account.print_general_ledger.start'
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

    @staticmethod
    def default_fiscalyear():
        FiscalYear = Pool().get('account.fiscalyear')
        return FiscalYear.find(
            Transaction().context.get('company'), exception=False)

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_posted():
        return False

    @staticmethod
    def default_empty_account():
        return False

    def on_change_fiscalyear(self):
        return {
            'start_period': None,
            'end_period': None,
            }


class PrintGeneralLedger(Wizard):
    'Print General Ledger'
    __name__ = 'account.print_general_ledger'
    start = StateView('account.print_general_ledger.start',
        'account.print_general_ledger_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateAction('account.report_general_ledger')

    def do_print_(self, action):
        if self.start.start_period:
            start_period = self.start.start_period.id
        else:
            start_period = None
        if self.start.end_period:
            end_period = self.start.end_period.id
        else:
            end_period = None
        data = {
            'company': self.start.company.id,
            'fiscalyear': self.start.fiscalyear.id,
            'start_period': start_period,
            'end_period': end_period,
            'posted': self.start.posted,
            'empty_account': self.start.empty_account,
            }
        return action, data

    def transition_print_(self):
        return 'end'


class GeneralLedger(Report):
    __name__ = 'account.general_ledger'

    @classmethod
    def parse(cls, report, objects, data, localcontext):
        pool = Pool()
        Account = pool.get('account.account')
        Period = pool.get('account.period')
        Company = pool.get('company.company')

        company = Company(data['company'])

        accounts = Account.search([
                ('company', '=', data['company']),
                ('kind', '!=', 'view'),
                ], order=[('code', 'ASC'), ('id', 'ASC')])

        start_period_ids = [0]
        start_periods = []
        if data['start_period']:
            start_period = Period(data['start_period'])
            start_periods = Period.search([
                    ('fiscalyear', '=', data['fiscalyear']),
                    ('end_date', '<=', start_period.start_date),
                    ])
            start_period_ids = [p.id for p in start_periods]

        with Transaction().set_context(
                fiscalyear=data['fiscalyear'],
                periods=start_period_ids,
                posted=data['posted']):
            start_accounts = Account.browse(accounts)
        id2start_account = {}
        for account in start_accounts:
            id2start_account[account.id] = account

        end_period_ids = []
        if data['end_period']:
            end_period = Period(data['end_period'])
            end_periods = Period.search([
                    ('fiscalyear', '=', data['fiscalyear']),
                    ('end_date', '<=', end_period.start_date),
                    ])
            if end_period not in end_periods:
                end_periods.append(end_period)
        else:
            end_periods = Period.search([
                    ('fiscalyear', '=', data['fiscalyear']),
                    ])
        end_period_ids = [p.id for p in end_periods]

        with Transaction().set_context(
                fiscalyear=data['fiscalyear'],
                periods=end_period_ids,
                posted=data['posted']):
            end_accounts = Account.browse(accounts)
        id2end_account = {}
        for account in end_accounts:
            id2end_account[account.id] = account

        periods = end_periods
        periods.sort(lambda x, y: cmp(x.start_date, y.start_date))
        localcontext['start_period'] = periods[0]
        periods.sort(lambda x, y: cmp(x.end_date, y.end_date))
        localcontext['end_period'] = periods[-1]

        if not data['empty_account']:
            account2lines = cls.get_lines(accounts,
                end_periods, data['posted'])
            for account in (set(accounts) - set(account2lines)):
                accounts.remove(account)

        account_id2lines = cls.lines(accounts,
            list(set(end_periods).difference(set(start_periods))),
            data['posted'])

        localcontext['accounts'] = accounts
        localcontext['id2start_account'] = id2start_account
        localcontext['id2end_account'] = id2end_account
        localcontext['digits'] = company.currency.digits
        localcontext['lines'] = lambda account_id: account_id2lines[account_id]
        localcontext['company'] = company

        return super(GeneralLedger, cls).parse(report, objects, data,
            localcontext)

    @classmethod
    def get_lines(cls, accounts, periods, posted):
        MoveLine = Pool().get('account.move.line')
        clause = [
            ('account', 'in', [a.id for a in accounts]),
            ('period', 'in', [p.id for p in periods]),
            ('state', '!=', 'draft'),
            ]
        if posted:
            clause.append(('move.state', '=', 'posted'))
        moves = MoveLine.search(clause, order=[])
        res = {}
        for move in moves:
            res.setdefault(move.account, []).append(move)
        return res

    @classmethod
    def lines(cls, accounts, periods, posted):
        Move = Pool().get('account.move')
        res = dict((a.id, []) for a in accounts)
        account2lines = cls.get_lines(accounts, periods, posted)

        state_selections = dict(Move.fields_get(
                fields_names=['state'])['state']['selection'])

        for account, lines in account2lines.iteritems():
            lines.sort(lambda x, y: cmp(x.date, y.date))
            balance = Decimal('0.0')
            for line in lines:
                balance += line.debit - line.credit
                res[account.id].append({
                        'date': line.date,
                        'move': line.move.rec_name,
                        'debit': line.debit,
                        'credit': line.credit,
                        'balance': balance,
                        'description': '\n'.join(
                            (line.move.description or '',
                                line.description or '')).strip(),
                        'origin': (line.move.origin.rec_name
                            if line.move.origin else ''),
                        'state': state_selections.get(line.move.state,
                            line.move.state),
                        })
        return res


class PrintTrialBalanceStart(ModelView):
    'Print Trial Balance'
    __name__ = 'account.print_trial_balance.start'
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

    @staticmethod
    def default_fiscalyear():
        FiscalYear = Pool().get('account.fiscalyear')
        return FiscalYear.find(
            Transaction().context.get('company'), exception=False)

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_posted():
        return False

    @staticmethod
    def default_empty_account():
        return False

    def on_change_fiscalyear(self):
        return {
            'start_period': None,
            'end_period': None,
            }


class PrintTrialBalance(Wizard):
    'Print Trial Balance'
    __name__ = 'account.print_trial_balance'
    start = StateView('account.print_trial_balance.start',
        'account.print_trial_balance_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateAction('account.report_trial_balance')

    def do_print_(self, action):
        if self.start.start_period:
            start_period = self.start.start_period.id
        else:
            start_period = None
        if self.start.end_period:
            end_period = self.start.end_period.id
        else:
            end_period = None
        data = {
            'company': self.start.company.id,
            'fiscalyear': self.start.fiscalyear.id,
            'start_period': start_period,
            'end_period': end_period,
            'posted': self.start.posted,
            'empty_account': self.start.empty_account,
            }
        return action, data

    def transition_print_(self):
        return 'end'


class TrialBalance(Report):
    __name__ = 'account.trial_balance'

    @classmethod
    def parse(cls, report, objects, data, localcontext):
        pool = Pool()
        Account = pool.get('account.account')
        Period = pool.get('account.period')
        Company = pool.get('company.company')

        company = Company(data['company'])

        accounts = Account.search([
                ('company', '=', data['company']),
                ('kind', '!=', 'view'),
                ])

        start_periods = []
        if data['start_period']:
            start_period = Period(data['start_period'])
            start_periods = Period.search([
                    ('fiscalyear', '=', data['fiscalyear']),
                    ('end_date', '<=', start_period.start_date),
                    ])

        if data['end_period']:
            end_period = Period(data['end_period'])
            end_periods = Period.search([
                    ('fiscalyear', '=', data['fiscalyear']),
                    ('end_date', '<=', end_period.start_date),
                    ])
            end_periods = list(set(end_periods).difference(
                    set(start_periods)))
            if end_period not in end_periods:
                end_periods.append(end_period)
        else:
            end_periods = Period.search([
                    ('fiscalyear', '=', data['fiscalyear']),
                    ])
            end_periods = list(set(end_periods).difference(
                    set(start_periods)))

        start_period_ids = [p.id for p in start_periods] or [0]
        end_period_ids = [p.id for p in end_periods]

        with Transaction().set_context(
                fiscalyear=data['fiscalyear'],
                periods=start_period_ids,
                posted=data['posted']):
            start_accounts = Account.browse(accounts)

        with Transaction().set_context(
                fiscalyear=None,
                periods=end_period_ids,
                posted=data['posted']):
            in_accounts = Account.browse(accounts)

        with Transaction().set_context(
                fiscalyear=data['fiscalyear'],
                periods=start_period_ids + end_period_ids,
                posted=data['posted']):
            end_accounts = Account.browse(accounts)

        to_remove = []
        if not data['empty_account']:
            for account in in_accounts:
                if account.debit == Decimal('0.0') \
                        and account.credit == Decimal('0.0'):
                    to_remove.append(account.id)

        accounts = []
        for start_account, in_account, end_account in izip(
                start_accounts, in_accounts, end_accounts):
            if in_account.id in to_remove:
                continue
            accounts.append({
                    'code': start_account.code,
                    'name': start_account.name,
                    'start_balance': start_account.balance,
                    'debit': in_account.debit,
                    'credit': in_account.credit,
                    'end_balance': end_account.balance,
                    })

        periods = end_periods

        localcontext['accounts'] = accounts
        periods.sort(key=operator.attrgetter('start_date'))
        localcontext['start_period'] = periods[0]
        periods.sort(key=operator.attrgetter('end_date'))
        localcontext['end_period'] = periods[-1]
        localcontext['company'] = company
        localcontext['digits'] = company.currency.digits
        localcontext['sum'] = lambda accounts, field: cls.sum(accounts, field)

        return super(TrialBalance, cls).parse(report, objects, data,
            localcontext)

    @classmethod
    def sum(cls, accounts, field):
        amount = Decimal('0.0')
        for account in accounts:
            amount += account[field]
        return amount


class OpenBalanceSheetStart(ModelView):
    'Open Balance Sheet'
    __name__ = 'account.open_balance_sheet.start'
    date = fields.Date('Date', required=True)
    company = fields.Many2One('company.company', 'Company', required=True)
    posted = fields.Boolean('Posted Move', help='Show only posted move')

    @staticmethod
    def default_date():
        Date_ = Pool().get('ir.date')
        return Date_.today()

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_posted():
        return False


class OpenBalanceSheet(Wizard):
    'Open Balance Sheet'
    __name__ = 'account.open_balance_sheet'
    start = StateView('account.open_balance_sheet.start',
        'account.open_balance_sheet_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Open', 'open_', 'tryton-ok', default=True),
            ])
    open_ = StateAction('account.act_account_balance_sheet_tree')

    def do_open_(self, action):
        pool = Pool()
        Lang = pool.get('ir.lang')

        company = self.start.company
        lang, = Lang.search([
                ('code', '=', Transaction().language),
                ])

        date = Lang.strftime(self.start.date, lang.code, lang.date)

        action['pyson_context'] = PYSONEncoder().encode({
                'date': Date(self.start.date.year,
                    self.start.date.month,
                    self.start.date.day),
                'posted': self.start.posted,
                'company': company.id,
                })
        action['name'] += ' %s - %s' % (date, company.rec_name)
        return action, {}

    def transition_open_(self):
        return 'end'


class OpenIncomeStatementStart(ModelView):
    'Open Income Statement'
    __name__ = 'account.open_income_statement.start'
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

    @staticmethod
    def default_fiscalyear():
        FiscalYear = Pool().get('account.fiscalyear')
        return FiscalYear.find(
            Transaction().context.get('company'), exception=False)

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_posted():
        return False

    def on_change_fiscalyear(self):
        return {
            'start_period': None,
            'end_period': None,
        }


class OpenIncomeStatement(Wizard):
    'Open Income Statement'
    __name__ = 'account.open_income_statement'
    start = StateView('account.open_income_statement.start',
        'account.open_income_statement_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Open', 'open_', 'tryton-ok', default=True),
            ])
    open_ = StateAction('account.act_account_income_statement_tree')

    def do_open_(self, action):
        pool = Pool()
        Period = pool.get('account.period')

        start_periods = []
        if self.start.start_period:
            start_periods = Period.search([
                    ('fiscalyear', '=', self.start.fiscalyear.id),
                    ('end_date', '<=', self.start.start_period.start_date),
                    ])

        end_periods = []
        if self.start.end_period:
            end_periods = Period.search([
                    ('fiscalyear', '=', self.start.fiscalyear.id),
                    ('end_date', '<=', self.start.end_period.start_date),
                    ])
            end_periods = list(set(end_periods).difference(
                    set(start_periods)))
            if self.start.end_period not in end_periods:
                end_periods.append(self.start.end_period)
        else:
            end_periods = Period.search([
                    ('fiscalyear', '=', self.start.fiscalyear.id),
                    ])
            end_periods = list(set(end_periods).difference(
                    set(start_periods)))

        action['pyson_context'] = PYSONEncoder().encode({
                'periods': [p.id for p in end_periods],
                'posted': self.start.posted,
                'company': self.start.company.id,
                })
        return action, {}


class CreateChartStart(ModelView):
    'Create Chart'
    __name__ = 'account.create_chart.start'


class CreateChartAccount(ModelView):
    'Create Chart'
    __name__ = 'account.create_chart.account'
    company = fields.Many2One('company.company', 'Company', required=True)
    account_template = fields.Many2One('account.account.template',
            'Account Template', required=True, domain=[('parent', '=', None)])

    @staticmethod
    def default_company():
        return Transaction().context.get('company')


class CreateChartProperties(ModelView):
    'Create Chart'
    __name__ = 'account.create_chart.properties'
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


class CreateChart(Wizard):
    'Create Chart'
    __name__ = 'account.create_chart'
    start = StateView('account.create_chart.start',
        'account.create_chart_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Ok', 'account', 'tryton-ok', default=True),
            ])
    account = StateView('account.create_chart.account',
        'account.create_chart_account_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'create_account', 'tryton-ok', default=True),
            ])
    create_account = StateTransition()
    properties = StateView('account.create_chart.properties',
        'account.create_chart_properties_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'create_properties', 'tryton-ok', default=True),
            ])
    create_properties = StateTransition()

    def transition_create_account(self):
        pool = Pool()
        TaxCodeTemplate = pool.get('account.tax.code.template')
        TaxTemplate = pool.get('account.tax.template')
        TaxRuleTemplate = pool.get('account.tax.rule.template')
        TaxRuleLineTemplate = \
            pool.get('account.tax.rule.line.template')
        Config = pool.get('ir.configuration')

        with Transaction().set_context(language=Config.get_language()):
            account_template = self.account.account_template

            # Create account types
            template2type = {}
            account_template.type.create_type(self.account.company.id,
                template2type=template2type)

            # Create accounts
            template2account = {}
            account_template.create_account(self.account.company.id,
                template2account=template2account, template2type=template2type)

            # Create tax codes
            template2tax_code = {}
            tax_code_templates = TaxCodeTemplate.search([
                    ('account', '=', account_template.id),
                    ('parent', '=', None),
                    ])
            for tax_code_template in tax_code_templates:
                tax_code_template.create_tax_code(self.account.company.id,
                    template2tax_code=template2tax_code)

            # Create taxes
            template2tax = {}
            tax_templates = TaxTemplate.search([
                    ('account', '=', account_template.id),
                    ('parent', '=', None),
                    ])
            for tax_template in tax_templates:
                tax_template.create_tax(self.account.company.id,
                    template2tax_code=template2tax_code,
                    template2account=template2account,
                    template2tax=template2tax)

            # Update taxes on accounts
            account_template.update_account_taxes(template2account,
                template2tax)

            # Create tax rules
            template2rule = {}
            tax_rule_templates = TaxRuleTemplate.search([
                    ('account', '=', account_template.id),
                    ])
            for tax_rule_template in tax_rule_templates:
                tax_rule_template.create_rule(self.account.company.id,
                    template2rule=template2rule)

            # Create tax rule lines
            template2rule_line = {}
            tax_rule_line_templates = TaxRuleLineTemplate.search([
                    ('rule.account', '=', account_template.id),
                    ])
            for tax_rule_line_template in tax_rule_line_templates:
                tax_rule_line_template.create_rule_line(template2tax,
                    template2rule, template2rule_line=template2rule_line)
        return 'properties'

    def default_properties(self, fields):
        return {
            'company': self.account.company.id,
            }

    def transition_create_properties(self):
        pool = Pool()
        Property = pool.get('ir.property')
        ModelField = pool.get('ir.model.field')

        with Transaction().set_context(company=self.properties.company.id):
            account_receivable_field, = ModelField.search([
                    ('model.model', '=', 'party.party'),
                    ('name', '=', 'account_receivable'),
                    ], limit=1)
            properties = Property.search([
                    ('field', '=', account_receivable_field.id),
                    ('res', '=', None),
                    ('company', '=', self.properties.company.id),
                    ])
            with Transaction().set_user(0):
                Property.delete(properties)
                if self.properties.account_receivable:
                    Property.create([{
                                'field': account_receivable_field.id,
                                'value': str(
                                    self.properties.account_receivable),
                                'company': self.properties.company.id,
                                }])

            account_payable_field, = ModelField.search([
                    ('model.model', '=', 'party.party'),
                    ('name', '=', 'account_payable'),
                    ], limit=1)
            properties = Property.search([
                    ('field', '=', account_payable_field.id),
                    ('res', '=', None),
                    ('company', '=', self.properties.company.id),
                    ])
            with Transaction().set_user(0):
                Property.delete(properties)
                if self.properties.account_payable:
                    Property.create([{
                                'field': account_payable_field.id,
                                'value': str(self.properties.account_payable),
                                'company': self.properties.company.id,
                                }])
        return 'end'


class UpdateChartStart(ModelView):
    'Update Chart'
    __name__ = 'account.update_chart.start'
    account = fields.Many2One('account.account', 'Root Account',
            required=True, domain=[('parent', '=', None)])


class UpdateChartSucceed(ModelView):
    'Update Chart'
    __name__ = 'account.update_chart.succeed'


class UpdateChart(Wizard):
    'Update Chart'
    __name__ = 'account.update_chart'
    start = StateView('account.update_chart.start',
        'account.update_chart_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Update', 'update', 'tryton-ok', default=True),
            ])
    update = StateTransition()
    succeed = StateView('account.update_chart.succeed',
        'account.update_chart_succeed_view_form', [
            Button('Ok', 'end', 'tryton-ok', default=True),
            ])

    def transition_update(self):
        pool = Pool()
        TaxCode = pool.get('account.tax.code')
        TaxCodeTemplate = pool.get('account.tax.code.template')
        Tax = pool.get('account.tax')
        TaxTemplate = pool.get('account.tax.template')
        TaxRule = pool.get('account.tax.rule')
        TaxRuleTemplate = pool.get('account.tax.rule.template')
        TaxRuleLine = pool.get('account.tax.rule.line')
        TaxRuleLineTemplate = \
            pool.get('account.tax.rule.line.template')

        account = self.start.account

        # Update account types
        template2type = {}
        account.type.update_type(template2type=template2type)
        # Create missing account types
        if account.type.template:
            account.type.template.create_type(account.company.id,
                template2type=template2type)

        # Update accounts
        template2account = {}
        account.update_account(template2account=template2account,
            template2type=template2type)
        # Create missing accounts
        if account.template:
            account.template.create_account(account.company.id,
                template2account=template2account, template2type=template2type)

        # Update tax codes
        template2tax_code = {}
        tax_codes = TaxCode.search([
            ('company', '=', account.company.id),
            ('parent', '=', None),
            ])
        for tax_code in tax_codes:
            tax_code.update_tax_code(template2tax_code=template2tax_code)
        # Create missing tax codes
        if account.template:
            tax_code_templates = TaxCodeTemplate.search([
                ('account', '=', account.template.id),
                ('parent', '=', None),
                ])
            for tax_code_template in tax_code_templates:
                tax_code_template.create_tax_code(account.company.id,
                    template2tax_code=template2tax_code)

        # Update taxes
        template2tax = {}
        taxes = Tax.search([
            ('company', '=', account.company.id),
            ('parent', '=', None),
            ])
        for tax in taxes:
            tax.update_tax(template2tax_code=template2tax_code,
                    template2account=template2account,
                    template2tax=template2tax)
        # Create missing taxes
        if account.template:
            tax_templates = TaxTemplate.search([
                ('account', '=', account.template.id),
                ('parent', '=', None),
                ])
            for tax_template in tax_templates:
                tax_template.create_tax(account.company.id,
                        template2tax_code=template2tax_code,
                        template2account=template2account,
                        template2tax=template2tax)

        # Update taxes on accounts
        account.update_account_taxes(template2account, template2tax)

        # Update tax rules
        template2rule = {}
        tax_rules = TaxRule.search([
            ('company', '=', account.company.id),
            ])
        for tax_rule in tax_rules:
            tax_rule.update_rule(template2rule=template2rule)
        # Create missing tax rules
        if account.template:
            tax_rule_templates = TaxRuleTemplate.search([
                ('account', '=', account.template.id),
                ])
            for tax_rule_template in tax_rule_templates:
                tax_rule_template.create_rule(account.company.id,
                    template2rule=template2rule)

        # Update tax rule lines
        template2rule_line = {}
        tax_rule_lines = TaxRuleLine.search([
            ('rule.company', '=', account.company.id),
            ])
        for tax_rule_line in tax_rule_lines:
            tax_rule_line.update_rule_line(template2tax, template2rule,
                template2rule_line=template2rule_line)
        # Create missing tax rule lines
        if account.template:
            tax_rule_line_templates = TaxRuleLineTemplate.search([
                ('rule.account', '=', account.template.id),
                ])
            for tax_rule_line_template in tax_rule_line_templates:
                tax_rule_line_template.create_rule_line(template2tax,
                    template2rule, template2rule_line=template2rule_line)
        return 'succeed'


class OpenThirdPartyBalanceStart(ModelView):
    'Open Third Party Balance'
    __name__ = 'account.open_third_party_balance.start'
    company = fields.Many2One('company.company', 'Company', required=True)
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
            required=True)
    posted = fields.Boolean('Posted Move', help='Show only posted move')

    @staticmethod
    def default_fiscalyear():
        Fiscalyear = Pool().get('account.fiscalyear')
        return Fiscalyear.find(
            Transaction().context.get('company'), exception=False)

    @staticmethod
    def default_posted():
        return False

    @staticmethod
    def default_company():
        return Transaction().context.get('company')


class OpenThirdPartyBalance(Wizard):
    'Open Third Party Balance'
    __name__ = 'account.open_third_party_balance'
    start = StateView('account.open_third_party_balance.start',
        'account.open_balance_sheet_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateAction('account.report_third_party_balance')

    def do_print_(self, action):
        data = {
            'company': self.start.company.id,
            'fiscalyear': self.start.fiscalyear.id,
            'posted': self.start.posted,
            }
        return action, data

    def transition_print_(self):
        return 'end'


class ThirdPartyBalance(Report):
    __name__ = 'account.third_party_balance'

    @classmethod
    def parse(cls, report, objects, data, localcontext):
        pool = Pool()
        Party = pool.get('party.party')
        MoveLine = pool.get('account.move.line')
        Company = pool.get('company.company')
        Date = pool.get('ir.date')
        cursor = Transaction().cursor

        company = Company(data['company'])
        localcontext['company'] = company
        localcontext['digits'] = company.currency.digits
        localcontext['fiscalyear'] = data['fiscalyear']
        with Transaction().set_context(context=localcontext):
            line_query, _ = MoveLine.query_get()
        if data['posted']:
            posted_clause = "AND m.state = 'posted' "
        else:
            posted_clause = ""

        cursor.execute('SELECT l.party, SUM(l.debit), SUM(l.credit) '
                'FROM account_move_line l '
                    'JOIN account_move m ON (l.move = m.id) '
                    'JOIN account_account a ON (l.account = a.id) '
                'WHERE l.party IS NOT NULL '
                    'AND a.active '
                    'AND a.kind IN (\'payable\',\'receivable\') '
                    'AND l.reconciliation IS NULL '
                    'AND a.company = %s '
                    'AND (l.maturity_date <= %s '
                        'OR l.maturity_date IS NULL) '
                    'AND ' + line_query + ' '
                    + posted_clause +
                'GROUP BY l.party '
                'HAVING (SUM(l.debit) != 0 OR SUM(l.credit) != 0)',
                (data['company'], Date.today()))

        res = cursor.fetchall()
        id2party = {}
        for party in Party.browse([x[0] for x in res]):
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

        return super(ThirdPartyBalance, cls).parse(report, objects, data,
            localcontext)


class OpenAgedBalanceStart(ModelView):
    'Open Aged Balance'
    __name__ = 'account.open_aged_balance.start'
    company = fields.Many2One('company.company', 'Company', required=True)
    balance_type = fields.Selection(
        [('customer', 'Customer'), ('supplier', 'Supplier'), ('both', 'Both')],
        "Type", required=True)
    term1 = fields.Integer("First Term", required=True)
    term2 = fields.Integer("Second Term", required=True)
    term3 = fields.Integer("Third Term", required=True)
    unit = fields.Selection(
        [('day', 'Day'), ('month', 'Month')], "Unit", required=True)
    posted = fields.Boolean('Posted Move', help='Show only posted move')

    @staticmethod
    def default_balance_type():
        return "customer"

    @staticmethod
    def default_posted():
        return False

    @staticmethod
    def default_term1():
        return 30

    @staticmethod
    def default_term2():
        return 60

    @staticmethod
    def default_term3():
        return 90

    @staticmethod
    def default_unit():
        return 'day'

    @staticmethod
    def default_company():
        return Transaction().context.get('company')


class OpenAgedBalance(Wizard):
    'Open Aged Party Balance'
    __name__ = 'account.open_aged_balance'
    start = StateView('account.open_aged_balance.start',
        'account.open_aged_balance_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateAction('account.report_aged_balance')

    @classmethod
    def __setup__(cls):
        super(OpenAgedBalance, cls).__setup__()
        cls._error_messages.update({
                'warning': 'Warning',
                'term_overlap_desc': 'You cannot define overlapping terms',
                })

    def do_print_(self, action):
        if not (self.start.term1 < self.start.term2 < self.start.term3):
            self.raise_user_error(error="warning",
                error_description="term_overlap_desc")
        data = {
            'company': self.start.company.id,
            'term1': self.start.term1,
            'term2': self.start.term2,
            'term3': self.start.term3,
            'unit': self.start.unit,
            'posted': self.start.posted,
            'balance_type': self.start.balance_type,
            }
        return action, data

    def transition_print_(self):
        return 'end'


class AgedBalance(Report):
    __name__ = 'account.aged_balance'

    @classmethod
    def parse(cls, report, objects, data, localcontext):
        pool = Pool()
        Party = pool.get('party.party')
        MoveLine = pool.get('account.move.line')
        Company = pool.get('company.company')
        Date = pool.get('ir.date')
        cursor = Transaction().cursor

        company = Company(data['company'])
        localcontext['digits'] = company.currency.digits
        localcontext['posted'] = data['posted']
        with Transaction().set_context(context=localcontext):
            line_query, _ = MoveLine.query_get()

        terms = (data['term1'], data['term2'], data['term3'])
        if data['unit'] == 'month':
            coef = datetime.timedelta(days=30)
        else:
            coef = datetime.timedelta(days=1)

        kind = {
            'both': ('payable', 'receivable'),
            'supplier': ('payable',),
            'customer': ('receivable',),
            }[data['balance_type']]

        res = {}
        for position, term in enumerate(terms):
            if position == 2:
                term_query = 'l.maturity_date <= %s'
                term_args = (Date.today() - term * coef,)
            else:
                term_query = '(l.maturity_date <= %s '\
                    'AND l.maturity_date > %s) '
                term_args = (
                    Date.today() - term * coef,
                    Date.today() - terms[position + 1] * coef)

            cursor.execute('SELECT l.party, SUM(l.debit) - SUM(l.credit) '
                'FROM account_move_line l '
                'JOIN account_move m ON (l.move = m.id) '
                'JOIN account_account a ON (l.account = a.id) '
                'WHERE l.party IS NOT NULL '
                    'AND a.active '
                    'AND a.kind IN (' + ','.join(('%s',) * len(kind)) + ") "
                    'AND l.reconciliation IS NULL '
                    'AND a.company = %s '
                    'AND ' + term_query + ' '
                    'AND ' + line_query + ' '
                    'GROUP BY l.party '
                    'HAVING (SUM(l.debit) - SUM(l.credit) != 0)',
                kind + (data['company'],) + term_args)
            for party, solde in cursor.fetchall():
                if party in res:
                    res[party][position] = solde
                else:
                    res[party] = [(i[0] == position) and solde
                        or Decimal("0.0") for i in enumerate(terms)]
        parties = Party.search([
            ('id', 'in', [k for k in res.iterkeys()]),
            ])

        localcontext['main_title'] = data['balance_type']
        localcontext['unit'] = data['unit']
        for i in range(3):
            localcontext['total' + str(i)] = sum(
                (v[i] for v in res.itervalues()))
            localcontext['term' + str(i)] = terms[i]

        localcontext['company'] = company
        localcontext['parties'] = [{
                'name': p.rec_name,
                'amount0': res[p.id][0],
                'amount1': res[p.id][1],
                'amount2': res[p.id][2],
                } for p in parties]

        return super(AgedBalance, cls).parse(report, objects, data,
            localcontext)
