#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, fields
from trytond.pyson import Eval, Or
from trytond.backend import TableHandler
from trytond.transaction import Transaction
from trytond.pool import PoolMeta

__all__ = ['Category', 'CategoryCustomerTax', 'CategorySupplierTax',
    'Template', 'TemplateCustomerTax', 'TemplateSupplierTax']
__metaclass__ = PoolMeta


class Category:
    __name__ = 'product.category'
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
        'category', 'tax', 'Customer Taxes',
        domain=[('parent', '=', None), ['OR',
                ('group', '=', None),
                ('group.kind', 'in', ['sale', 'both'])],
            ],
        states={
            'invisible': (~Eval('context', {}).get('company')
                | Eval('taxes_parent')),
            },
        depends=['taxes_parent'])
    supplier_taxes = fields.Many2Many('product.category-supplier-account.tax',
        'category', 'tax', 'Supplier Taxes',
        domain=[('parent', '=', None), ['OR',
                ('group', '=', None),
                ('group.kind', 'in', ['purchase', 'both'])],
            ],
        states={
            'invisible': (~Eval('context', {}).get('company')
                | Eval('taxes_parent')),
            },
        depends=['taxes_parent'])
    customer_taxes_used = fields.Function(fields.One2Many('account.tax', None,
            'Customer Taxes Used'), 'get_taxes')
    supplier_taxes_used = fields.Function(fields.One2Many('account.tax', None,
            'Supplier Taxes Used'), 'get_taxes')

    @classmethod
    def __setup__(cls):
        super(Category, cls).__setup__()
        cls._error_messages.update({
            'missing_account': ('There is no account '
                    'expense/revenue defined on the category '
                    '%s (%d)'),
            })
        cls.parent.states['required'] = Or(
            cls.parent.states.get('required', False),
            Eval('account_parent', False) | Eval('taxes_parent', False))
        cls.parent.depends.extend(['account_parent', 'taxes_parent'])

    def get_account(self, name):
        if self.account_parent:
            return getattr(self.parent, name).id
        elif getattr(self, name[:-5]):
            return getattr(self, name[:-5]).id
        else:
            self.raise_user_error('missing_account', (self.name, self.id))

    def get_taxes(self, name):
        if self.taxes_parent:
            return [x.id for x in getattr(self.parent, name)]
        else:
            return [x.id for x in getattr(self, name[:-5])]

    def on_change_account_expense(self):
        supplier_taxes = []
        result = {
            'supplier_taxes': supplier_taxes,
            }
        if self.account_expense:
            supplier_taxes.extend(tax.id for tax in self.account_expense.taxes)
        return result

    def on_change_account_revenue(self):
        customer_taxes = []
        result = {
            'customer_taxes': customer_taxes,
            }
        if self.account_revenue:
            customer_taxes.extend(tax.id for tax in self.account_revenue.taxes)
        return result


class CategoryCustomerTax(ModelSQL):
    'Category - Customer Tax'
    __name__ = 'product.category-customer-account.tax'
    _table = 'product_category_customer_taxes_rel'
    category = fields.Many2One('product.category', 'Category',
            ondelete='CASCADE', select=True, required=True)
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
            required=True)

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        # Migration from 1.6 product renamed into category
        table = TableHandler(cursor, cls)
        if table.column_exist('product'):
            table.index_action('product', action='remove')
            table.drop_fk('product')
            table.column_rename('product', 'category')
        super(CategoryCustomerTax, cls).__register__(module_name)


class CategorySupplierTax(ModelSQL):
    'Category - Supplier Tax'
    __name__ = 'product.category-supplier-account.tax'
    _table = 'product_category_supplier_taxes_rel'
    category = fields.Many2One('product.category', 'Category',
            ondelete='CASCADE', select=True, required=True)
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
            required=True)

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        # Migration from 1.6 product renamed into category
        table = TableHandler(cursor, cls)
        if table.column_exist('product'):
            table.index_action('product', action='remove')
            table.drop_fk('product')
            table.column_rename('product', 'category')
        super(CategorySupplierTax, cls).__register__(module_name)


class Template:
    __name__ = 'product.template'
    account_category = fields.Boolean('Use Category\'s accounts',
            help='Use the accounts defined on the category')
    account_expense = fields.Property(fields.Many2One('account.account',
            'Account Expense', domain=[
                ('kind', '=', 'expense'),
                ('company', '=', Eval('context', {}).get('company', 0)),
                ], on_change=['account_category', 'account_expense'],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_category')),
                },
            help='This account will be used instead of the one defined'
            ' on the category.', depends=['account_category']))
    account_revenue = fields.Property(fields.Many2One('account.account',
            'Account Revenue', domain=[
                ('kind', '=', 'revenue'),
                ('company', '=', Eval('context', {}).get('company', 0)),
                ], on_change=['account_category', 'account_revenue'],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_category')),
                },
            help='This account will be used instead of the one defined'
            ' on the category.', depends=['account_category']))
    account_expense_used = fields.Function(fields.Many2One('account.account',
        'Account Expense Used'), 'get_account')
    account_revenue_used = fields.Function(fields.Many2One('account.account',
        'Account Revenue Used'), 'get_account')
    taxes_category = fields.Boolean('Use Category\'s Taxes',
            help='Use the taxes defined on the category')
    customer_taxes = fields.Many2Many('product.template-customer-account.tax',
        'product', 'tax', 'Customer Taxes',
        domain=[('parent', '=', None), ['OR',
                ('group', '=', None),
                ('group.kind', 'in', ['sale', 'both'])],
            ],
        states={
            'invisible': (~Eval('context', {}).get('company')
                | Eval('taxes_category')),
            }, depends=['taxes_category'])
    supplier_taxes = fields.Many2Many('product.template-supplier-account.tax',
        'product', 'tax', 'Supplier Taxes',
        domain=[('parent', '=', None), ['OR',
                ('group', '=', None),
                ('group.kind', 'in', ['purchase', 'both'])],
            ],
        states={
            'invisible': (~Eval('context', {}).get('company')
                | Eval('taxes_category')),
            }, depends=['taxes_category'])
    customer_taxes_used = fields.Function(fields.One2Many('account.tax', None,
        'Customer Taxes Used'), 'get_taxes')
    supplier_taxes_used = fields.Function(fields.One2Many('account.tax', None,
        'Supplier Taxes Used'), 'get_taxes')

    @classmethod
    def __setup__(cls):
        super(Template, cls).__setup__()
        cls._error_messages.update({
                'missing_account': ('There is no account '
                    'expense/revenue defined on the product %s (%d)'),
                })
        cls.category.states['required'] = Or(
            cls.category.states.get('required', False),
            Eval('account_category', False) | Eval('taxes_category', False))
        cls.category.depends.extend(['account_category', 'taxes_category'])

    @staticmethod
    def default_taxes_category():
        return None

    def get_account(self, name):
        if self.account_category:
            return getattr(self.category, name).id
        elif getattr(self, name[:-5]):
            return getattr(self, name[:-5]).id
        else:
            self.raise_user_error('missing_account', (self.name, self.id))

    def get_taxes(self, name):
        if self.taxes_category:
            return [x.id for x in getattr(self.category, name)]
        else:
            return [x.id for x in getattr(self, name[:-5])]

    def on_change_account_expense(self):
        result = {}
        if not self.account_category:
            supplier_taxes = []
            result = {
                'supplier_taxes': supplier_taxes,
            }
            if self.account_expense:
                supplier_taxes.extend(
                    tax.id for tax in self.account_expense.taxes)
        return result

    def on_change_account_revenue(self):
        result = {}
        if not self.account_category:
            customer_taxes = []
            result = {
                'customer_taxes': customer_taxes,
            }
            if self.account_revenue:
                customer_taxes.extend(
                    tax.id for tax in self.account_revenue.taxes)
        return result


class TemplateCustomerTax(ModelSQL):
    'Product Template - Customer Tax'
    __name__ = 'product.template-customer-account.tax'
    _table = 'product_customer_taxes_rel'
    product = fields.Many2One('product.template', 'Product Template',
            ondelete='CASCADE', select=True, required=True)
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
            required=True)


class TemplateSupplierTax(ModelSQL):
    'Product Template - Supplier Tax'
    __name__ = 'product.template-supplier-account.tax'
    _table = 'product_supplier_taxes_rel'
    product = fields.Many2One('product.template', 'Product Template',
            ondelete='CASCADE', select=True, required=True)
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
            required=True)
