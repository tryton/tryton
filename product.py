# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import copy

from trytond.model import ModelSQL, fields
from trytond.pyson import Eval, Or, Bool
from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

__all__ = ['Category', 'CategoryCustomerTax', 'CategorySupplierTax',
    'Template', 'TemplateCustomerTax', 'TemplateSupplierTax', 'Product',
    'MissingFunction']


class MissingFunction(fields.Function):
    '''Function field that will raise the error
    when the value is accessed and is None'''

    def __init__(self, field, error, getter, setter=None, searcher=None,
            loading='lazy'):
        super(MissingFunction, self).__init__(field, getter, setter=setter,
            searcher=searcher, loading=loading)
        self.error = error

    def __copy__(self):
        return MissingFunction(copy.copy(self._field), self.error, self.getter,
            setter=self.setter, searcher=self.searcher)

    def __deepcopy__(self, memo):
        return MissingFunction(copy.deepcopy(self._field, memo), self.error,
            self.getter, setter=self.setter, searcher=self.searcher)

    def __get__(self, inst, cls):
        value = super(MissingFunction, self).__get__(inst, cls)
        if inst is not None and value is None:
            inst.raise_user_error(self.error, (inst.name, inst.id))
        return value


class Category:
    __metaclass__ = PoolMeta
    __name__ = 'product.category'
    accounting = fields.Boolean('Accounting', select=True,
        states={
            'readonly': Bool(Eval('childs', [0])) | Bool(Eval('parent')),
            },
        depends=['parent'])
    account_parent = fields.Boolean('Use Parent\'s accounts',
        states={
            'invisible': ~Eval('accounting', False),
            },
        depends=['accounting'],
        help='Use the accounts defined on the parent category')
    account_expense = fields.Property(fields.Many2One('account.account',
            'Account Expense', domain=[
                ('kind', '=', 'expense'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_parent')
                    | ~Eval('accounting', False)),
                },
            depends=['account_parent', 'accounting']))
    account_revenue = fields.Property(fields.Many2One('account.account',
            'Account Revenue', domain=[
                ('kind', '=', 'revenue'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_parent')
                    | ~Eval('accounting', False)),
                },
            depends=['account_parent', 'accounting']))
    account_expense_used = MissingFunction(fields.Many2One('account.account',
            'Account Expense Used'), 'missing_account', 'get_account')
    account_revenue_used = MissingFunction(fields.Many2One('account.account',
            'Account Revenue Used'), 'missing_account', 'get_account')
    taxes_parent = fields.Boolean('Use the Parent\'s Taxes',
        states={
            'invisible': ~Eval('accounting', False),
            },
        depends=['accounting'],
        help='Use the taxes defined on the parent category')
    customer_taxes = fields.Many2Many('product.category-customer-account.tax',
        'category', 'tax', 'Customer Taxes',
        order=[('tax.sequence', 'ASC'), ('tax.id', 'ASC')],
        domain=[('parent', '=', None), ['OR',
                ('group', '=', None),
                ('group.kind', 'in', ['sale', 'both'])],
            ],
        states={
            'invisible': (~Eval('context', {}).get('company')
                | Eval('taxes_parent')
                | ~Eval('accounting', False)),
            },
        depends=['taxes_parent', 'accounting'])
    supplier_taxes = fields.Many2Many('product.category-supplier-account.tax',
        'category', 'tax', 'Supplier Taxes',
        order=[('tax.sequence', 'ASC'), ('tax.id', 'ASC')],
        domain=[('parent', '=', None), ['OR',
                ('group', '=', None),
                ('group.kind', 'in', ['purchase', 'both'])],
            ],
        states={
            'invisible': (~Eval('context', {}).get('company')
                | Eval('taxes_parent')
                | ~Eval('accounting', False)),
            },
        depends=['taxes_parent', 'accounting'])
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
        cls.parent.domain = [
            ('accounting', '=', Eval('accounting', False)),
            cls.parent.domain or []]
        cls.parent.depends.append('accounting')
        cls.parent.states['required'] = Or(
            cls.parent.states.get('required', False),
            Eval('account_parent', False) | Eval('taxes_parent', False))
        cls.parent.depends.extend(['account_parent', 'taxes_parent'])

    @classmethod
    def default_accounting(cls):
        return False

    def get_account(self, name):
        if self.account_parent:
            # Use __getattr__ to avoid raise of exception
            account = self.parent.__getattr__(name)
        else:
            account = getattr(self, name[:-5])
        return account.id if account else None

    def get_taxes(self, name):
        if self.taxes_parent:
            return [x.id for x in getattr(self.parent, name)]
        else:
            return [x.id for x in getattr(self, name[:-5])]

    @fields.depends('parent', 'accounting')
    def on_change_with_accounting(self):
        if self.parent:
            return self.parent.accounting
        return self.accounting

    @fields.depends('account_expense')
    def on_change_account_expense(self):
        if self.account_expense:
            self.supplier_taxes = self.account_expense.taxes
        else:
            self.supplier_taxes = []

    @fields.depends('account_revenue')
    def on_change_account_revenue(self):
        if self.account_revenue:
            self.customer_taxes = self.account_revenue.taxes
        else:
            self.customer_taxes = []

    @classmethod
    def view_attributes(cls):
        return super(Category, cls).view_attributes() + [
            ('/form/notebook/page[@id="accounting"]', 'states', {
                    'invisible': ~Eval('accounting', False),
                    }),
            ]


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
        TableHandler = backend.get('TableHandler')
        # Migration from 1.6 product renamed into category
        table = TableHandler(cls)
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
        TableHandler = backend.get('TableHandler')
        # Migration from 1.6 product renamed into category
        table = TableHandler(cls)
        if table.column_exist('product'):
            table.index_action('product', action='remove')
            table.drop_fk('product')
            table.column_rename('product', 'category')
        super(CategorySupplierTax, cls).__register__(module_name)


class Template:
    __metaclass__ = PoolMeta
    __name__ = 'product.template'
    account_category = fields.Many2One('product.category', 'Account Category',
        domain=[
            ('accounting', '=', True),
            ],
        states={
            'required': (Eval('accounts_category', False)
                | Eval('taxes_category', False)),
            },
        depends=['accounts_category', 'taxes_category'])
    accounts_category = fields.Boolean('Use Category\'s accounts',
            help='Use the accounts defined on the category')
    account_expense = fields.Property(fields.Many2One('account.account',
            'Account Expense', domain=[
                ('kind', '=', 'expense'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('accounts_category')),
                },
            help='This account will be used instead of the one defined'
            ' on the category.', depends=['accounts_category']))
    account_revenue = fields.Property(fields.Many2One('account.account',
            'Account Revenue', domain=[
                ('kind', '=', 'revenue'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('accounts_category')),
                },
            help='This account will be used instead of the one defined'
            ' on the category.', depends=['accounts_category']))
    account_expense_used = MissingFunction(fields.Many2One('account.account',
        'Account Expense Used'), 'missing_account', 'get_account')
    account_revenue_used = MissingFunction(fields.Many2One('account.account',
        'Account Revenue Used'), 'missing_account', 'get_account')
    taxes_category = fields.Boolean('Use Category\'s Taxes',
            help='Use the taxes defined on the category')
    customer_taxes = fields.Many2Many('product.template-customer-account.tax',
        'product', 'tax', 'Customer Taxes',
        order=[('tax.sequence', 'ASC'), ('tax.id', 'ASC')],
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
        order=[('tax.sequence', 'ASC'), ('tax.id', 'ASC')],
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

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        pool = Pool()
        Category = pool.get('product.category')
        sql_table = cls.__table__()
        category = Category.__table__()

        table = TableHandler(cls, module_name)
        category_exists = table.column_exist('category')

        # Migration from 3.8: rename account_category into accounts_category
        if table.column_exist('account_category'):
            table.column_rename('account_category', 'accounts_category')

        super(Template, cls).__register__(module_name)

        # Migration from 3.8: duplicate category into account_category
        if category_exists:
            # Only accounting category until now
            cursor.execute(*category.update([category.accounting], [True]))
            cursor.execute(*sql_table.update(
                    [sql_table.account_category],
                    [sql_table.category]))

    @classmethod
    def default_accounts_category(cls):
        pool = Pool()
        Config = pool.get('product.configuration')
        return Config(1).default_accounts_category

    @classmethod
    def default_taxes_category(cls):
        pool = Pool()
        Config = pool.get('product.configuration')
        return Config(1).default_taxes_category

    def get_account(self, name):
        if self.accounts_category:
            account = self.account_category.__getattr__(name)
        else:
            account = getattr(self, name[:-5])
        return account.id if account else None

    def get_taxes(self, name):
        if self.taxes_category:
            return [x.id for x in getattr(self.account_category, name)]
        else:
            return [x.id for x in getattr(self, name[:-5])]

    @fields.depends('account_category', 'account_expense')
    def on_change_account_expense(self):
        if not self.account_category:
            if self.account_expense:
                self.supplier_taxes = self.account_expense.taxes
            else:
                self.supplier_taxes = []

    @fields.depends('account_category', 'account_revenue')
    def on_change_account_revenue(self):
        if not self.account_category:
            if self.account_revenue:
                self.customer_taxes = self.account_revenue.taxes
            else:
                self.customer_taxes = []


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


class Product:
    __metaclass__ = PoolMeta
    __name__ = 'product.product'
    # Avoid raise of UserError from MissingFunction
    account_expense_used = fields.Function(fields.Many2One('account.account',
        'Account Expense Used'), 'get_template')
    account_revenue_used = fields.Function(fields.Many2One('account.account',
        'Account Revenue Used'), 'get_template')
    customer_taxes_used = fields.Function(fields.One2Many('account.tax', None,
            'Customer Taxes Used'), 'get_template')
    supplier_taxes_used = fields.Function(fields.One2Many('account.tax', None,
            'Supplier Taxes Used'), 'get_template')
