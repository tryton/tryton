# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.model import fields
from trytond.pyson import Eval
from trytond import backend
from trytond.transaction import Transaction


__all__ = ['Configuration', 'ProductConfiguration']


class Configuration:
    __metaclass__ = PoolMeta
    __name__ = 'account.configuration'

    default_product_account_expense = fields.Function(fields.Many2One(
            'account.account', 'Default Account Expense',
            domain=[
                ('kind', '=', 'expense'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ]),
        'get_account', setter='set_account')
    default_product_account_revenue = fields.Function(fields.Many2One(
            'account.account', 'Default Account Revenue',
            domain=[
                ('kind', '=', 'revenue'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ]),
        'get_account', setter='set_account')
    default_category_account_expense = fields.Function(fields.Many2One(
            'account.account', 'Default Account Expense',
            domain=[
                ('kind', '=', 'expense'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ]),
        'get_account', setter='set_account')
    default_category_account_revenue = fields.Function(fields.Many2One(
            'account.account', 'Default Account Revenue',
            domain=[
                ('kind', '=', 'revenue'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ]),
        'get_account', setter='set_account')

    @classmethod
    def _get_account_field(cls, name):
        pool = Pool()
        ModelField = pool.get('ir.model.field')
        if name in ['default_product_account_expense',
                'default_product_account_revenue']:
            field, = ModelField.search([
                    ('model.model', '=', 'product.template'),
                    ('name', '=', name[len('default_product_'):]),
                    ], limit=1)
            return field
        elif name in ['default_category_account_expense',
                'default_category_account_revenue']:
            field, = ModelField.search([
                    ('model.model', '=', 'product.category'),
                    ('name', '=', name[len('default_category_'):]),
                    ], limit=1)
            return field
        return super(Configuration, cls)._get_account_field(name)


class ProductConfiguration:
    __metaclass__ = PoolMeta
    __name__ = 'product.configuration'

    default_accounts_category = fields.Boolean(
        'Use Category\'s accounts by default')
    default_taxes_category = fields.Boolean(
        'Use Category\' taxes by default')

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')

        # Migration from 3.8: rename default_account_category into
        # default_accounts_category
        table = TableHandler(cls, module_name)
        if table.column_exist('default_account_category'):
            table.column_rename('default_account_category',
                'default_accounts_category', exception=True)

        super(ProductConfiguration, cls).__register__(module_name)

    @classmethod
    def default_default_accounts_category(cls):
        return False

    @classmethod
    def default_default_taxes_category(cls):
        return False
