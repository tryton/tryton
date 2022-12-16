# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from functools import wraps

from sql import Null

from trytond.i18n import gettext
from trytond.model import ModelSQL, fields
from trytond.pyson import Eval, Or, Bool
from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.tools.multivalue import migrate_property
from trytond.modules.company.model import (
    CompanyMultiValueMixin, CompanyValueMixin)

from .exceptions import AccountError, TaxError


def account_used(field_name, field_string=None):
    def decorator(func):
        @wraps(func)
        def wrapper(self):
            account = func(self)
            if not account:
                account = self.get_account(field_name + '_used')
            # Allow empty values on on_change
            if not account and not Transaction().readonly:
                Model = self.__class__
                field = field_name
                if field_string:
                    if getattr(self, field_string, None):
                        Model = getattr(self, field_string).__class__
                    else:
                        field = field_string
                field = (
                    Model.fields_get([field])[field]['string'])
                raise AccountError(
                    gettext('account_product.msg_missing_account',
                        field=field,
                        name=self.rec_name))
            if account:
                return account.current()
        return wrapper
    return decorator


def template_property(field_name):
    @property
    def prop(self):
        return getattr(self.template, field_name)
    return prop


class Category(CompanyMultiValueMixin, metaclass=PoolMeta):
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
                ('closed', '!=', True),
                ('type.expense', '=', True),
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
                ('closed', '!=', True),
                ('type.revenue', '=', True),
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
    customer_taxes_used = fields.Function(fields.Many2Many(
            'account.tax', None, None, "Customer Taxes Used"), 'get_taxes')
    supplier_taxes_used = fields.Function(fields.Many2Many(
            'account.tax', None, None, "Supplier Taxes Used"), 'get_taxes')

    @classmethod
    def __setup__(cls):
        super(Category, cls).__setup__()
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

    @fields.depends('parent', '_parent_parent.accounting', 'accounting')
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
            ('type.expense', '=', True),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    account_revenue = fields.Many2One(
        'account.account', "Account Revenue",
        domain=[
            ('type.revenue', '=', True),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])

    @classmethod
    def __register__(cls, module_name):
        exist = backend.TableHandler.table_exist(cls._table)

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


class CategorySupplierTax(ModelSQL):
    'Category - Supplier Tax'
    __name__ = 'product.category-supplier-account.tax'
    _table = 'product_category_supplier_taxes_rel'
    category = fields.Many2One('product.category', 'Category',
            ondelete='CASCADE', select=True, required=True)
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
            required=True)


class Template(CompanyMultiValueMixin, metaclass=PoolMeta):
    __name__ = 'product.template'
    account_category = fields.Many2One('product.category', 'Account Category',
        domain=[
            ('accounting', '=', True),
            ])

    def get_account(self, name, **pattern):
        if self.account_category:
            return self.account_category.get_account(name, **pattern)

    def get_taxes(self, name):
        if self.account_category:
            return getattr(self.account_category, name)

    @property
    @account_used('account_expense', 'account_category')
    def account_expense_used(self):
        pass

    @property
    @account_used('account_revenue', 'account_category')
    def account_revenue_used(self):
        pass

    @property
    def customer_taxes_used(self):
        taxes = self.get_taxes('customer_taxes_used')
        if taxes is None:
            account = self.account_revenue_used
            if account:
                taxes = account.taxes
        if taxes is None:
            # Allow empty values on on_change
            if Transaction().readonly:
                taxes = []
            else:
                raise TaxError(
                    gettext('account_product.msg_missing_taxes',
                        name=self.rec_name))
        return taxes

    @property
    def supplier_taxes_used(self):
        taxes = self.get_taxes('supplier_taxes_used')
        if taxes is None:
            account = self.account_expense_used
            if account:
                taxes = account.taxes
        if taxes is None:
            # Allow empty values on on_change
            if Transaction().readonly:
                taxes = []
            else:
                raise TaxError(
                    gettext('account_product.msg_missing_taxes',
                        name=self.rec_name))
        return taxes


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'
    account_expense_used = template_property('account_expense_used')
    account_revenue_used = template_property('account_revenue_used')
    customer_taxes_used = template_property('customer_taxes_used')
    supplier_taxes_used = template_property('supplier_taxes_used')


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


class TemplateCategoryAll(metaclass=PoolMeta):
    __name__ = 'product.template-product.category.all'

    @classmethod
    def union_models(cls):
        return super(TemplateCategoryAll, cls).union_models() + [
            'product.template-product.category.account']
