#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval
from trytond.backend import TableHandler
from trytond.transaction import Transaction
from trytond.pool import Pool


class Category(ModelSQL, ModelView):
    _name = 'product.category'

    account_expense = fields.Property(fields.Many2One('account.account',
            'Account Expense', domain=[
                ('kind', '=', 'expense'),
                ('company', '=', Eval('context', {}).get('company', 0)),
                ], on_change=['account_expense'],
            states={
                'invisible': ~Eval('context', {}).get('company'),
                }))
    account_revenue = fields.Property(fields.Many2One( 'account.account',
            'Account Revenue', domain=[
                ('kind', '=', 'revenue'),
                ('company', '=', Eval('context', {}).get('company', 0)),
                ], on_change=['account_revenue'],
            states={
                'invisible': ~Eval('context', {}).get('company'),
                }))
    customer_taxes = fields.Many2Many('product.category-customer-account.tax',
            'category', 'tax', 'Customer Taxes', domain=[('parent', '=', False)])
    supplier_taxes = fields.Many2Many('product.category-supplier-account.tax',
            'category', 'tax', 'Supplier Taxes', domain=[('parent', '=', False)])

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
            ondelete='CASCADE', select=1, required=True)
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
            ondelete='CASCADE', select=1, required=True)
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
        'product', 'tax', 'Customer Taxes', domain=[('parent', '=', False)],
        states={
            'invisible': (~Eval('context', {}).get('company')
                | Eval('taxes_category')),
            }, depends=['taxes_category'])
    supplier_taxes = fields.Many2Many('product.template-supplier-account.tax',
        'product', 'tax', 'Supplier Taxes', domain=[('parent', '=', False)],
        states={
            'invisible': (~Eval('context', {}).get('company')
                | Eval('taxes_category')),
            }, depends=['taxes_category'])
    customer_taxes_used = fields.Function(fields.One2Many('account.tax', None,
        'Customer Taxes Used'), 'get_taxes')
    supplier_taxes_used = fields.Function(fields.One2Many('account.tax', None,
        'Customer Taxes Used'), 'get_taxes')

    def __init__(self):
        super(Template, self).__init__()
        self._error_messages.update({
            'missing_account': 'There is no account ' \
                    'expense/revenue defined on the product ' \
                    '%s (%d)',
            })

    def default_taxes_category(self):
        return False

    def get_account(self, ids, name):
        account_obj = Pool().get('account.account')
        res = {}
        name = name[:-5]
        for product in self.browse(ids):
            if product[name]:
                res[product.id] = product[name].id
            else:
                if product.category[name]:
                    res[product.id] = product.category[name].id
                else:
                    self.raise_user_error('missing_account',
                            (product.name, product.id))
        return res

    def get_taxes(self, ids, name):
        res = {}
        name = name[:-5]
        for product in self.browse(ids):
            if product.taxes_category:
                res[product.id] = [x.id for x in product.category[name]]
            else:
                res[product.id] = [x.id for x in product[name]]
        return res

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
            ondelete='CASCADE', select=1, required=True)
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
            required=True)

TemplateCustomerTax()


class TemplateSupplierTax(ModelSQL):
    'Product Template - Supplier Tax'
    _name = 'product.template-supplier-account.tax'
    _table = 'product_supplier_taxes_rel'
    _description = __doc__
    product = fields.Many2One('product.template', 'Product Template',
            ondelete='CASCADE', select=1, required=True)
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
            required=True)

TemplateSupplierTax()
