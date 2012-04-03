#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import copy
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval, Or
from trytond.backend import TableHandler
from trytond.transaction import Transaction
from trytond.pool import Pool


class Category(ModelSQL, ModelView):
    _name = 'product.category'

    account_parent = fields.Boolean('Use Parent\'s accounts',
        help='Use the accounts defined on the parent category')
    account_expense = fields.Property(fields.Many2One('account.account',
            'Account Expense', domain=[
                ('kind', '=', 'expense'),
                ('company', '=', Eval('context', {}).get('company', 0)),
                ], on_change=['account_expense'],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_parent')),
                },
            depends=['account_parent']))
    account_revenue = fields.Property(fields.Many2One('account.account',
            'Account Revenue', domain=[
                ('kind', '=', 'revenue'),
                ('company', '=', Eval('context', {}).get('company', 0)),
                ], on_change=['account_revenue'],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_parent')),
                },
            depends=['account_parent']))
    account_expense_used = fields.Function(fields.Many2One('account.account',
            'Account Expense Used'), 'get_account')
    account_revenue_used = fields.Function(fields.Many2One('account.account',
            'Account Revenue Used'), 'get_account')
    taxes_parent = fields.Boolean('Use the Parent\'s Taxes',
        help='Use the taxes defined on the parent category')
    customer_taxes = fields.Many2Many('product.category-customer-account.tax',
        'category', 'tax', 'Customer Taxes', domain=[('parent', '=', None)],
        states={
            'invisible': (~Eval('context', {}).get('company')
                | Eval('taxes_parent')),
            },
        depends=['taxes_parent'])
    supplier_taxes = fields.Many2Many('product.category-supplier-account.tax',
        'category', 'tax', 'Supplier Taxes', domain=[('parent', '=', None)],
        states={
            'invisible': (~Eval('context', {}).get('company')
                | Eval('taxes_parent')),
            },
        depends=['taxes_parent'])
    customer_taxes_used = fields.Function(fields.One2Many('account.tax', None,
            'Customer Taxes Used'), 'get_taxes')
    supplier_taxes_used = fields.Function(fields.One2Many('account.tax', None,
            'Supplier Taxes Used'), 'get_taxes')

    def __init__(self):
        super(Category, self).__init__()
        self._error_messages.update({
            'missing_account': ('There is no account '
                    'expense/revenue defined on the category '
                    '%s (%d)'),
            })
        self.parent = copy.copy(self.parent)
        self.parent.states = copy.copy(self.parent.states)
        self.parent.states['required'] = Or(
            self.parent.states.get('required', False),
            Eval('account_parent', False) | Eval('taxes_parent', False))
        self.parent.depends = copy.copy(self.parent.depends)
        self.parent.depends.extend(['account_parent', 'taxes_parent'])
        self._reset_columns()

    def get_account(self, ids, name):
        accounts = {}
        for category in self.browse(ids):
            if category.account_parent:
                accounts[category.id] = category.parent[name].id
            elif category[name[:-5]]:
                accounts[category.id] = category[name[:-5]].id
            else:
                self.raise_user_error('missing_account',
                    (category.name, category.id))
        return accounts

    def get_taxes(self, ids, name):
        taxes = {}
        for category in self.browse(ids):
            if category.taxes_parent:
                taxes[category.id] = [x.id for x in category.parent[name]]
            else:
                taxes[category.id] = [x.id for x in category[name[:-5]]]
        return taxes

    def on_change_account_expense(self, values):
        account_obj = Pool().get('account.account')
        supplier_taxes = []
        result = {
            'supplier_taxes': supplier_taxes,
        }
        if values.get('account_expense'):
            account = account_obj.browse(values['account_expense'])
            supplier_taxes.extend(tax.id for tax in account.taxes)
        return result

    def on_change_account_revenue(self, values):
        account_obj = Pool().get('account.account')
        customer_taxes = []
        result = {
            'customer_taxes': customer_taxes,
        }
        if values.get('account_revenue'):
            account = account_obj.browse(values['account_revenue'])
            customer_taxes.extend(tax.id for tax in account.taxes)
        return result

Category()


class CategoryCustomerTax(ModelSQL):
    'Category - Customer Tax'
    _name = 'product.category-customer-account.tax'
    _table = 'product_category_customer_taxes_rel'
    _description = __doc__
    category = fields.Many2One('product.category', 'Category',
            ondelete='CASCADE', select=True, required=True)
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
            required=True)

    def init(self, module_name):
        cursor = Transaction().cursor
        # Migration from 1.6 product renamed into category
        table = TableHandler(cursor, self)
        if table.column_exist('product'):
            table.index_action('product', action='remove')
            table.drop_fk('product')
            table.column_rename('product', 'category')
        super(CategoryCustomerTax, self).init(module_name)

CategoryCustomerTax()


class CategorySupplierTax(ModelSQL):
    'Category - Supplier Tax'
    _name = 'product.category-supplier-account.tax'
    _table = 'product_category_supplier_taxes_rel'
    _description = __doc__
    category = fields.Many2One('product.category', 'Category',
            ondelete='CASCADE', select=True, required=True)
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
            required=True)

    def init(self, module_name):
        cursor = Transaction().cursor
        # Migration from 1.6 product renamed into category
        table = TableHandler(cursor, self)
        if table.column_exist('product'):
            table.index_action('product', action='remove')
            table.drop_fk('product')
            table.column_rename('product', 'category')
        super(CategorySupplierTax, self).init(module_name)

CategorySupplierTax()


class Template(ModelSQL, ModelView):
    _name = 'product.template'

    account_category = fields.Boolean('Use Category\'s accounts',
            help='Use the accounts defined on the category')
    account_expense = fields.Property(fields.Many2One('account.account',
            'Account Expense', domain=[
                ('kind', '=', 'expense'),
                ('company', '=', Eval('context', {}).get('company', 0)),
                ], on_change=['account_expense'],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_category')),
                }, help='This account will be used instead of the one defined'\
                    ' on the category.', depends=['account_category']))
    account_revenue = fields.Property(fields.Many2One('account.account',
                'Account Revenue', domain=[
                    ('kind', '=', 'revenue'),
                    ('company', '=', Eval('context', {}).get('company', 0)),
                    ], on_change=['account_revenue'],
                states={
                    'invisible': (~Eval('context', {}).get('company')
                        | Eval('account_category')),
                    },
                help='This account will be used instead of the one defined'\
                    ' on the category.', depends=['account_category']))
    account_expense_used = fields.Function(fields.Many2One('account.account',
        'Account Expense Used'), 'get_account')
    account_revenue_used = fields.Function(fields.Many2One('account.account',
        'Account Revenue Used'), 'get_account')
    taxes_category = fields.Boolean('Use Category\'s Taxes',
            help='Use the taxes defined on the category')
    customer_taxes = fields.Many2Many('product.template-customer-account.tax',
        'product', 'tax', 'Customer Taxes', domain=[('parent', '=', None)],
        states={
            'invisible': (~Eval('context', {}).get('company')
                | Eval('taxes_category')),
            }, depends=['taxes_category'])
    supplier_taxes = fields.Many2Many('product.template-supplier-account.tax',
        'product', 'tax', 'Supplier Taxes', domain=[('parent', '=', None)],
        states={
            'invisible': (~Eval('context', {}).get('company')
                | Eval('taxes_category')),
            }, depends=['taxes_category'])
    customer_taxes_used = fields.Function(fields.One2Many('account.tax', None,
        'Customer Taxes Used'), 'get_taxes')
    supplier_taxes_used = fields.Function(fields.One2Many('account.tax', None,
        'Supplier Taxes Used'), 'get_taxes')

    def __init__(self):
        super(Template, self).__init__()
        self._error_messages.update({
            'missing_account': 'There is no account ' \
                    'expense/revenue defined on the product ' \
                    '%s (%d)',
            })
        self.category = copy.copy(self.category)
        self.category.states = copy.copy(self.category.states)
        self.category.states['required'] = Or(
            self.category.states.get('required', False),
            Eval('account_category', False) | Eval('taxes_category', False))
        self.category.depends = copy.copy(self.category.depends)
        self.category.depends.extend(['account_category', 'taxes_category'])
        self._reset_columns()

    def default_taxes_category(self):
        return None

    def get_account(self, ids, name):
        accounts = {}
        for product in self.browse(ids):
            if product.account_category:
                accounts[product.id] = product.category[name].id
            elif product[name[:-5]]:
                accounts[product.id] = product[name[:-5]].id
            else:
                self.raise_user_error('missing_account',
                    (product.name, product.id))
        return accounts

    def get_taxes(self, ids, name):
        taxes = {}
        for product in self.browse(ids):
            if product.taxes_category:
                taxes[product.id] = [x.id for x in product.category[name]]
            else:
                taxes[product.id] = [x.id for x in product[name[:-5]]]
        return taxes

    def on_change_account_expense(self, values):
        account_obj = Pool().get('account.account')
        supplier_taxes = []
        result = {
            'supplier_taxes': supplier_taxes,
        }
        if values.get('account_expense'):
            account = account_obj.browse(values['account_expense'])
            supplier_taxes.extend(tax.id for tax in account.taxes)
        return result

    def on_change_account_revenue(self, values):
        account_obj = Pool().get('account.account')
        customer_taxes = []
        result = {
            'customer_taxes': customer_taxes,
        }
        if values.get('account_revenue'):
            account = account_obj.browse(values['account_revenue'])
            customer_taxes.extend(tax.id for tax in account.taxes)
        return result

Template()


class TemplateCustomerTax(ModelSQL):
    'Product Template - Customer Tax'
    _name = 'product.template-customer-account.tax'
    _table = 'product_customer_taxes_rel'
    _description = __doc__
    product = fields.Many2One('product.template', 'Product Template',
            ondelete='CASCADE', select=True, required=True)
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
            required=True)

TemplateCustomerTax()


class TemplateSupplierTax(ModelSQL):
    'Product Template - Supplier Tax'
    _name = 'product.template-supplier-account.tax'
    _table = 'product_supplier_taxes_rel'
    _description = __doc__
    product = fields.Many2One('product.template', 'Product Template',
            ondelete='CASCADE', select=True, required=True)
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
            required=True)

TemplateSupplierTax()
