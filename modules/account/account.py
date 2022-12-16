# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
import datetime
import operator
from itertools import izip, groupby
from functools import wraps

from sql import Column, Literal, Null
from sql.aggregate import Sum
from sql.conditionals import Coalesce

from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateView, StateAction, StateTransition, \
    Button
from trytond.report import Report
from trytond.tools import reduce_ids, grouped_slice
from trytond.pyson import Eval, PYSONEncoder, Date
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond import backend

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


def inactive_records(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with Transaction().set_context(active_test=False):
            return func(*args, **kwargs)
    return wrapper


class TypeTemplate(ModelSQL, ModelView):
    'Account Type Template'
    __name__ = 'account.account.type.template'
    name = fields.Char('Name', required=True, translate=True)
    parent = fields.Many2One('account.account.type.template', 'Parent',
            ondelete="RESTRICT")
    childs = fields.One2Many('account.account.type.template', 'parent',
        'Children')
    sequence = fields.Integer('Sequence')
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
        TableHandler = backend.get('TableHandler')
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
    def order_sequence(tables):
        table, _ = tables[None]
        return [table.sequence == Null, table.sequence]

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
        TableHandler = backend.get('TableHandler')
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
    def order_sequence(tables):
        table, _ = tables[None]
        return [table.sequence == Null, table.sequence]

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
                ('kind', '!=', 'view'),
                ])
        for account in accounts:
            type_sum[account.type.id] += (account.debit - account.credit)

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
                ('kind', '!=', 'view'),
                ])
        action['pyson_context'] = PYSONEncoder().encode({
                'date': Transaction().context.get('date'),
                'posted': Transaction().context.get('posted'),
                'cumulate': Transaction().context.get('cumulate'),
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
    party_required = fields.Boolean('Party Required',
        states={
            'invisible': Eval('kind') == 'view',
            },
        depends=['kind'])
    general_ledger_balance = fields.Boolean('General Ledger Balance',
        states={
            'invisible': Eval('kind') == 'view',
            },
        depends=['kind'],
        help="Display only the balance in the general ledger report")

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

    @staticmethod
    def default_party_required():
        return False

    @staticmethod
    def default_general_ledger_balance():
        return False

    def get_rec_name(self, name):
        if self.code:
            return self.code + ' - ' + self.name
        else:
            return self.name

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('code',) + tuple(clause[1:]),
            (cls._rec_name,) + tuple(clause[1:]),
            ]

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
        if not account or account.party_required != self.party_required:
            res['party_required'] = self.party_required
        if (not account
                or account.general_ledger_balance !=
                self.general_ledger_balance):
            res['general_ledger_balance'] = self.general_ledger_balance
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
                            ('add', [template2tax[x.id] for x in self.taxes])],
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
        left="left", right="right", ondelete="RESTRICT",
        domain=[('company', '=', Eval('company'))],
        depends=['company'])
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
    party_required = fields.Boolean('Party Required',
        states={
            'invisible': Eval('kind') == 'view',
            },
        depends=['kind'])
    general_ledger_balance = fields.Boolean('General Ledger Balance',
        states={
            'invisible': Eval('kind') == 'view',
            },
        depends=['kind'],
        help="Display only the balance in the general ledger report")
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
    def default_party_required():
        return False

    @staticmethod
    def default_general_ledger_balance():
        return False

    @staticmethod
    def default_kind():
        return 'view'

    def get_currency(self, name):
        return self.company.currency.id

    def get_currency_digits(self, name):
        return self.company.currency.digits

    @classmethod
    def get_balance(cls, accounts, name):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        FiscalYear = pool.get('account.fiscalyear')
        cursor = Transaction().cursor

        table_a = cls.__table__()
        table_c = cls.__table__()
        line = MoveLine.__table__()
        ids = [a.id for a in accounts]
        balances = dict((i, 0) for i in ids)
        line_query, fiscalyear_ids = MoveLine.query_get(line)
        for sub_ids in grouped_slice(ids):
            red_sql = reduce_ids(table_a.id, sub_ids)
            cursor.execute(*table_a.join(table_c,
                    condition=(table_c.left >= table_a.left)
                    & (table_c.right <= table_a.right)
                    ).join(line, condition=line.account == table_c.id
                    ).select(
                    table_a.id,
                    Sum(Coalesce(line.debit, 0) - Coalesce(line.credit, 0)),
                    where=red_sql & line_query & table_c.active,
                    group_by=table_a.id))
            result = cursor.fetchall()
            balances.update(dict(result))

        # SQLite uses float for SUM
        for account_id, balance in balances.iteritems():
            if isinstance(balance, Decimal):
                break
            balances[account_id] = Decimal(str(balance))

        for account in accounts:
            balances[account.id] = account.company.currency.round(
                balances[account.id])

        fiscalyears = FiscalYear.browse(fiscalyear_ids)
        func = lambda accounts, names: \
            {names[0]: cls.get_balance(accounts, names[0])}
        return cls._cumulate(fiscalyears, accounts, {name: balances},
            func)[name]

    @classmethod
    def get_credit_debit(cls, accounts, names):
        '''
        Function to compute debit, credit for accounts.
        If cumulate is set in the context, it is the cumulate amount over all
        previous fiscal year.
        '''
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        FiscalYear = pool.get('account.fiscalyear')
        cursor = Transaction().cursor

        result = {}
        ids = [a.id for a in accounts]
        for name in names:
            if name not in ('credit', 'debit'):
                raise Exception('Bad argument')
            result[name] = dict((i, 0) for i in ids)

        table = cls.__table__()
        line = MoveLine.__table__()
        line_query, fiscalyear_ids = MoveLine.query_get(line)
        columns = [table.id]
        for name in names:
            columns.append(Sum(Coalesce(Column(line, name), 0)))
        for sub_ids in grouped_slice(ids):
            red_sql = reduce_ids(table.id, sub_ids)
            cursor.execute(*table.join(line, 'LEFT',
                    condition=line.account == table.id
                    ).select(*columns,
                    where=red_sql & line_query,
                    group_by=table.id))
            for row in cursor.fetchall():
                account_id = row[0]
                for i, name in enumerate(names, 1):
                    # SQLite uses float for SUM
                    if not isinstance(row[i], Decimal):
                        result[name][account_id] = Decimal(str(row[i]))
                    else:
                        result[name][account_id] = row[i]
        for account in accounts:
            for name in names:
                result[name][account.id] = account.company.currency.round(
                    result[name][account.id])

        if not Transaction().context.get('cumulate'):
            return result
        else:
            fiscalyears = FiscalYear.browse(fiscalyear_ids)
            return cls._cumulate(fiscalyears, accounts, result,
                cls.get_credit_debit)

    @classmethod
    def _cumulate(cls, fiscalyears, accounts, values, func):
        """
        Cumulate previous fiscalyear values into values
        func is the method to compute values
        """
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')
        Deferral = pool.get('account.account.deferral')
        names = values.keys()

        youngest_fiscalyear = None
        for fiscalyear in fiscalyears:
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

        if not fiscalyear:
            return values

        if fiscalyear.state == 'close':
            id2deferral = {}
            ids = [a.id for a in accounts]
            for sub_ids in grouped_slice(ids):
                deferrals = Deferral.search([
                    ('fiscalyear', '=', fiscalyear.id),
                    ('account', 'in', list(sub_ids)),
                    ])
                for deferral in deferrals:
                    id2deferral[deferral.account.id] = deferral

            for account in accounts:
                if account.id in id2deferral:
                    deferral = id2deferral[account.id]
                    for name in names:
                        values[name][account.id] += getattr(deferral, name)
        else:
            with Transaction().set_context(fiscalyear=fiscalyear.id,
                    date=None, periods=None):
                previous_result = func(accounts, names)
            for name in names:
                vals = values[name]
                for account in accounts:
                    vals[account.id] += previous_result[name][account.id]

        return values

    def get_rec_name(self, name):
        if self.code:
            return self.code + ' - ' + self.name
        else:
            return self.name

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('code',) + tuple(clause[1:]),
            (cls._rec_name,) + tuple(clause[1:]),
            ]

    @classmethod
    def copy(cls, accounts, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default['left'] = 0
        default['right'] = 0
        default.setdefault('template')
        default.setdefault('deferrals', [])
        new_accounts = super(Account, cls).copy(accounts, default=default)
        cls._rebuild_tree('parent', None, 0)
        return new_accounts

    @classmethod
    def write(cls, *args):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        actions = iter(args)
        args = []
        for accounts, values in zip(actions, actions):
            if not values.get('active', True):
                childs = cls.search([
                        ('parent', 'child_of', [a.id for a in accounts]),
                        ])
                if MoveLine.search([
                            ('account', 'in', [a.id for a in childs]),
                            ]):
                    values = values.copy()
                    del values['active']
            args.extend((accounts, values))
        super(Account, cls).write(*args)

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
            if current_type != template_type:
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
    balance = fields.Function(fields.Numeric('Balance',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_balance')
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

    def get_balance(self, name):
        return self.debit - self.credit

    def get_currency_digits(self, name):
        return self.account.currency_digits

    def get_rec_name(self, name):
        return '%s - %s' % (self.account.rec_name, self.fiscalyear.rec_name)

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('account.rec_name',) + tuple(clause[1:]),
            ('fiscalyear.rec_name',) + tuple(clause[1:]),
            ]

    @classmethod
    def write(cls, deferrals, values, *args):
        cls.raise_user_error('write_deferral')


class OpenChartAccountStart(ModelView):
    'Open Chart of Accounts'
    __name__ = 'account.open_chart.start'
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
            help='Leave empty for all open fiscal year')
    posted = fields.Boolean('Posted Moves', help='Show posted moves only')

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
        required=True)
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

    @fields.depends('fiscalyear')
    def on_change_fiscalyear(self):
        self.start_period = None
        self.end_period = None


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
    def get_context(cls, records, data):
        report_context = super(GeneralLedger, cls).get_context(records, data)

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
            start_period_ids += [p.id for p in start_periods]
        else:
            start_period = None

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
            end_period = None
        end_period_ids = [p.id for p in end_periods]

        with Transaction().set_context(
                fiscalyear=data['fiscalyear'],
                periods=end_period_ids,
                posted=data['posted']):
            end_accounts = Account.browse(accounts)
        id2end_account = {}
        for account in end_accounts:
            id2end_account[account.id] = account

        if not data['empty_account']:
            account2lines = dict(cls.get_lines(accounts,
                    end_periods, data['posted']))
            accounts = Account.browse([a.id for a in accounts
                    if a in account2lines])

        account_id2lines = cls.lines(
            [a for a in accounts if not a.general_ledger_balance],
            list(set(end_periods).difference(set(start_periods))),
            data['posted'])

        report_context['accounts'] = accounts
        report_context['id2start_account'] = id2start_account
        report_context['id2end_account'] = id2end_account
        report_context['digits'] = company.currency.digits
        report_context['lines'] = \
            lambda account_id: account_id2lines[account_id]
        report_context['company'] = company
        report_context['start_period'] = start_period
        report_context['end_period'] = end_period

        return report_context

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
        lines = MoveLine.search(clause,
            order=[
                ('account.id', 'ASC'),
                ('date', 'ASC'),
                ])
        return groupby(lines, operator.attrgetter('account'))

    @classmethod
    def lines(cls, accounts, periods, posted):
        Move = Pool().get('account.move')
        res = dict((a.id, []) for a in accounts)
        account2lines = cls.get_lines(accounts, periods, posted)

        state_selections = dict(Move.fields_get(
                fields_names=['state'])['state']['selection'])

        for account, lines in account2lines:
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
        required=True)
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

    @fields.depends('fiscalyear')
    def on_change_fiscalyear(self):
        self.start_period = None
        self.end_period = None


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
    def get_context(cls, records, data):
        report_context = super(TrialBalance, cls).get_context(records, data)

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

        to_remove = set()
        if not data['empty_account']:
            for account in in_accounts:
                if account.debit == Decimal('0.0') \
                        and account.credit == Decimal('0.0'):
                    to_remove.add(account)

        accounts = []
        for start_account, in_account, end_account in izip(
                start_accounts, in_accounts, end_accounts):
            if in_account in to_remove:
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

        report_context['accounts'] = accounts
        periods.sort(key=operator.attrgetter('start_date'))
        report_context['start_period'] = periods[0]
        periods.sort(key=operator.attrgetter('end_date'))
        report_context['end_period'] = periods[-1]
        report_context['company'] = company
        report_context['digits'] = company.currency.digits
        report_context['sum'] = \
            lambda accounts, field: cls.sum(accounts, field)

        return report_context

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
                'cumulate': True,
                })
        action['name'] += ' %s - %s' % (date, company.rec_name)
        return action, {}

    def transition_open_(self):
        return 'end'


class OpenIncomeStatementStart(ModelView):
    'Open Income Statement'
    __name__ = 'account.open_income_statement.start'
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
        required=True)
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

    @fields.depends('fiscalyear')
    def on_change_fiscalyear(self):
        self.start_period = None
        self.end_period = None


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
            Button('OK', 'account', 'tryton-ok', default=True),
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

        with Transaction().set_context(language=Config.get_language(),
                company=self.account.company.id):
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
            Button('OK', 'end', 'tryton-ok', default=True),
            ])

    @inactive_records
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
        'account.open_third_party_balance_start_view_form', [
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
    def get_context(cls, records, data):
        report_context = super(ThirdPartyBalance, cls).get_context(records,
            data)

        pool = Pool()
        Party = pool.get('party.party')
        MoveLine = pool.get('account.move.line')
        Move = pool.get('account.move')
        Account = pool.get('account.account')
        Company = pool.get('company.company')
        Date = pool.get('ir.date')
        cursor = Transaction().cursor

        line = MoveLine.__table__()
        move = Move.__table__()
        account = Account.__table__()

        company = Company(data['company'])
        report_context['company'] = company
        report_context['digits'] = company.currency.digits
        report_context['fiscalyear'] = data['fiscalyear']
        with Transaction().set_context(context=report_context):
            line_query, _ = MoveLine.query_get(line)
        if data['posted']:
            posted_clause = move.state == 'posted'
        else:
            posted_clause = Literal(True)

        cursor.execute(*line.join(move, condition=line.move == move.id
                ).join(account, condition=line.account == account.id
                ).select(line.party, Sum(line.debit), Sum(line.credit),
                where=(line.party != Null)
                & account.active
                & account.kind.in_(('payable', 'receivable'))
                & (account.company == data['company'])
                & ((line.maturity_date <= Date.today())
                    | (line.maturity_date == Null))
                & line_query & posted_clause,
                group_by=line.party,
                having=(Sum(line.debit) != 0) | (Sum(line.credit) != 0)))

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
        report_context['total_debit'] = sum((x['debit'] for x in objects))
        report_context['total_credit'] = sum((x['credit'] for x in objects))
        report_context['total_solde'] = sum((x['solde'] for x in objects))
        report_context['records'] = objects

        return report_context


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
    def get_context(cls, records, data):
        report_context = super(AgedBalance, cls).get_context(records, data)

        pool = Pool()
        Party = pool.get('party.party')
        MoveLine = pool.get('account.move.line')
        Move = pool.get('account.move')
        Account = pool.get('account.account')
        Company = pool.get('company.company')
        Date = pool.get('ir.date')
        cursor = Transaction().cursor

        line = MoveLine.__table__()
        move = Move.__table__()
        account = Account.__table__()

        company = Company(data['company'])
        report_context['digits'] = company.currency.digits
        report_context['posted'] = data['posted']
        with Transaction().set_context(context=report_context):
            line_query, _ = MoveLine.query_get(line)

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
            term_query = line.maturity_date <= (Date.today() - term * coef)
            if position != 2:
                term_query &= line.maturity_date > (
                    Date.today() - terms[position + 1] * coef)

            cursor.execute(*line.join(move, condition=line.move == move.id
                    ).join(account, condition=line.account == account.id
                    ).select(line.party, Sum(line.debit) - Sum(line.credit),
                    where=(line.party != Null)
                    & account.active
                    & account.kind.in_(kind)
                    & (line.reconciliation == Null)
                    & (account.company == data['company'])
                    & term_query & line_query,
                    group_by=line.party,
                    having=(Sum(line.debit) - Sum(line.credit)) != 0))
            for party, solde in cursor.fetchall():
                if party in res:
                    res[party][position] = solde
                else:
                    res[party] = [(i[0] == position) and solde
                        or Decimal("0.0") for i in enumerate(terms)]
        parties = Party.search([
            ('id', 'in', [k for k in res.iterkeys()]),
            ])

        report_context['main_title'] = data['balance_type']
        report_context['unit'] = data['unit']
        for i in range(3):
            report_context['total' + str(i)] = sum(
                (v[i] for v in res.itervalues()))
            report_context['term' + str(i)] = terms[i]

        report_context['company'] = company
        report_context['parties'] = [{
                'name': p.rec_name,
                'amount0': res[p.id][0],
                'amount1': res[p.id][1],
                'amount2': res[p.id][2],
                } for p in parties]

        return report_context
