# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from functools import wraps

from sql import Null

from trytond.model import ModelSQL, fields
from trytond.pyson import Eval, Or, Bool
from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.tools.multivalue import migrate_property
from trytond.modules.company.model import (
    CompanyMultiValueMixin, CompanyValueMixin)

__all__ = ['Category', 'CategoryAccount',
    'CategoryCustomerTax', 'CategorySupplierTax',
    'Template', 'TemplateAccount',
    'TemplateCustomerTax', 'TemplateSupplierTax',
    'Product', 'account_used', 'template_property',
    'TemplateAccountCategory', 'TemplateCategoryAll']


def account_used(field_name):
    def decorator(func):
        @wraps(func)
        def wrapper(self):
            account = func(self)
            if not account:
                account = self.get_account(field_name + '_used')
            # Allow empty values on on_change
            if not account and not Transaction().readonly:
                field_string = (
                    self.fields_get([field_name])[field_name]['string'])
                self.raise_user_error('missing_account', {
                        'field': field_string,
                        'name': self.rec_name,
                        })
            return account
        return wrapper
    return decorator


def template_property(field_name):
    @property
    def prop(self):
        return getattr(self.template, field_name)
    return prop


class Category(CompanyMultiValueMixin):
    __metaclass__ = PoolMeta
    __name__ = 'product.category'
    accounting = fields.Boolean('Accounting', select=True,
        states={
            'readonly': Bool(Eval('childs', [0])) | Bool(Eval('parent')),
            },
        depends=['parent'],
        help="Check to convert into accounting category.")
    account_parent = fields.Boolean('Use Parent\'s accounts',
        states={
            'invisible': ~Eval('accounting', False),
            },
        depends=['accounting'],
        help="Use the accounts defined on the parent category.")
    accounts = fields.One2Many(
        'product.category.account', 'category', "Accounts")
    account_expense = fields.MultiValue(fields.Many2One('account.account',
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
    account_revenue = fields.MultiValue(fields.Many2One('account.account',
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
    taxes_parent = fields.Boolean('Use the Parent\'s Taxes',
        states={
            'invisible': ~Eval('accounting', False),
            },
        depends=['accounting'],
        help="Use the taxes defined on the parent category.")
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
        depends=['taxes_parent', 'accounting'],
        help="The taxes to apply when selling products of this category.")
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
        depends=['taxes_parent', 'accounting'],
        help="The taxes to apply when purchasing products of this category.")
    customer_taxes_used = fields.Function(fields.One2Many('account.tax', None,
            'Customer Taxes Used'), 'get_taxes')
    supplier_taxes_used = fields.Function(fields.One2Many('account.tax', None,
            'Supplier Taxes Used'), 'get_taxes')

    @classmethod
    def __setup__(cls):
        super(Category, cls).__setup__()
        cls._error_messages.update({
            'missing_account': ('There is no '
                    '"%(field)s" defined on the category "%(name)s"'),
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
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {'account_expense', 'account_revenue'}:
            return pool.get('product.category.account')
        return super(Category, cls).multivalue_model(field)

    @classmethod
    def default_accounting(cls):
        return False

    @classmethod
    def default_account_expense(cls, **pattern):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        config = Configuration(1)
        account = config.get_multivalue(
            'default_category_account_expense', **pattern)
        return account.id if account else None

    @classmethod
    def default_account_revenue(cls, **pattern):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        config = Configuration(1)
        account = config.get_multivalue(
            'default_category_account_revenue', **pattern)
        return account.id if account else None

    def get_account(self, name, **pattern):
        if self.account_parent:
            return self.parent.get_account(name, **pattern)
        else:
            return self.get_multivalue(name[:-5], **pattern)

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

    @property
    @account_used('account_expense')
    def account_expense_used(self):
        pass

    @property
    @account_used('account_revenue')
    def account_revenue_used(self):
        pass


class CategoryAccount(ModelSQL, CompanyValueMixin):
    "Category Account"
    __name__ = 'product.category.account'
    category = fields.Many2One(
        'product.category', "Category", ondelete='CASCADE', select=True)
    account_expense = fields.Many2One(
        'account.account', "Account Expense",
        domain=[
            ('kind', '=', 'expense'),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    account_revenue = fields.Many2One(
        'account.account', "Account Revenue",
        domain=[
            ('kind', '=', 'revenue'),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        exist = TableHandler.table_exist(cls._table)

        super(CategoryAccount, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.extend(['account_expense', 'account_revenue'])
        value_names.extend(['account_expense', 'account_revenue'])
        fields.append('company')
        migrate_property(
            'product.category', field_names, cls, value_names,
            parent='category', fields=fields)


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


class Template(CompanyMultiValueMixin):
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
            help="Check to use the accounts defined on the account category.")
    accounts = fields.One2Many(
        'product.template.account', 'template', "Accounts")
    account_expense = fields.MultiValue(fields.Many2One('account.account',
            'Account Expense', domain=[
                ('kind', '=', 'expense'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('accounts_category')),
                },
            help=("The account to use instead of the one defined on the "
                "account category."), depends=['accounts_category']))
    account_revenue = fields.MultiValue(fields.Many2One('account.account',
            'Account Revenue', domain=[
                ('kind', '=', 'revenue'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('accounts_category')),
                },
            help=("The account to use instead of the one defined on the "
                "account category."), depends=['accounts_category']))
    taxes_category = fields.Boolean('Use Category\'s Taxes',
            help="Check to use the taxes defined on the account category.")
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
            }, depends=['taxes_category'],
        help="The taxes to apply when selling the product.")
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
            }, depends=['taxes_category'],
        help="The taxes to apply when purchasing the product.")
    customer_taxes_used = fields.Function(fields.One2Many('account.tax', None,
        'Customer Taxes Used'), 'get_taxes')
    supplier_taxes_used = fields.Function(fields.One2Many('account.tax', None,
        'Supplier Taxes Used'), 'get_taxes')

    @classmethod
    def __setup__(cls):
        super(Template, cls).__setup__()
        cls._error_messages.update({
                'missing_account': ('There is no '
                    '"%(field)s" defined on the product "%(name)s"'),
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
        if (table.column_exist('account_category')
                and not table.column_exist('accounts_category')):
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
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {'account_expense', 'account_revenue'}:
            return pool.get('product.template.account')
        return super(Template, cls).multivalue_model(field)

    @classmethod
    def default_account_expense(cls, **pattern):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        config = Configuration(1)
        account = config.get_multivalue(
            'default_product_account_expense', **pattern)
        return account.id if account else None

    @classmethod
    def default_account_revenue(cls, **pattern):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        config = Configuration(1)
        account = config.get_multivalue(
            'default_product_account_revenue', **pattern)
        return account.id if account else None

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

    def get_account(self, name, **pattern):
        if self.accounts_category:
            return self.account_category.get_account(name, **pattern)
        else:
            return self.get_multivalue(name[:-5], **pattern)

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

    @property
    @account_used('account_expense')
    def account_expense_used(self):
        pass

    @property
    @account_used('account_revenue')
    def account_revenue_used(self):
        pass


class TemplateAccount(ModelSQL, CompanyValueMixin):
    "Product Template Account"
    __name__ = 'product.template.account'
    template = fields.Many2One(
        'product.template', "Template", ondelete='CASCADE', select=True)
    account_expense = fields.Many2One(
        'account.account', "Account Expense",
        domain=[
            ('kind', '=', 'expense'),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    account_revenue = fields.Many2One(
        'account.account', "Account Revenue",
        domain=[
            ('kind', '=', 'revenue'),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        exist = TableHandler.table_exist(cls._table)

        super(TemplateAccount, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.extend(['account_expense', 'account_revenue'])
        value_names.extend(['account_expense', 'account_revenue'])
        fields.append('company')
        migrate_property(
            'product.template', field_names, cls, value_names,
            parent='template', fields=fields)


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
    account_expense_used = template_property('account_expense_used')
    account_revenue_used = template_property('account_revenue_used')
    customer_taxes_used = fields.Function(fields.One2Many('account.tax', None,
            'Customer Taxes Used'), 'get_template')
    supplier_taxes_used = fields.Function(fields.One2Many('account.tax', None,
            'Supplier Taxes Used'), 'get_template')


class TemplateAccountCategory(ModelSQL):
    "Template - Account Category"
    __name__ = 'product.template-product.category.account'
    template = fields.Many2One('product.template', 'Template')
    category = fields.Many2One('product.category', 'Category')

    @classmethod
    def table_query(cls):
        pool = Pool()
        Template = pool.get('product.template')
        template = Template.__table__()
        return template.select(
            template.id.as_('id'),
            template.create_uid.as_('create_uid'),
            template.create_date.as_('create_date'),
            template.write_uid.as_('write_uid'),
            template.write_date.as_('write_date'),
            template.id.as_('template'),
            template.account_category.as_('category'),
            where=template.account_category != Null)


class TemplateCategoryAll:
    __metaclass__ = PoolMeta
    __name__ = 'product.template-product.category.all'

    @classmethod
    def union_models(cls):
        return super(TemplateCategoryAll, cls).union_models() + [
            'product.template-product.category.account']
