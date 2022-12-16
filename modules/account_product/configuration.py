# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.model import fields
from trytond.pyson import Eval
from trytond import backend


__all__ = ['Configuration', 'ConfigurationDefaultAccount',
    'ProductConfiguration']


class Configuration:
    __metaclass__ = PoolMeta
    __name__ = 'account.configuration'

    default_product_account_expense = fields.MultiValue(fields.Many2One(
            'account.account', 'Default Account Expense',
            domain=[
                ('kind', '=', 'expense'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ]))
    default_product_account_revenue = fields.MultiValue(fields.Many2One(
            'account.account', 'Default Account Revenue',
            domain=[
                ('kind', '=', 'revenue'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ]))
    default_category_account_expense = fields.MultiValue(fields.Many2One(
            'account.account', 'Default Account Expense',
            domain=[
                ('kind', '=', 'expense'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ]))
    default_category_account_revenue = fields.MultiValue(fields.Many2One(
            'account.account', 'Default Account Revenue',
            domain=[
                ('kind', '=', 'revenue'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ]))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {'default_product_account_expense',
                'default_product_account_revenue',
                'default_category_account_expense',
                'default_category_account_revenue'}:
            return pool.get('account.configuration.default_account')
        return super(Configuration, cls).multivalue_model(field)


class ConfigurationDefaultAccount:
    __metaclass__ = PoolMeta
    __name__ = 'account.configuration.default_account'
    default_product_account_expense = fields.Many2One(
        'account.account', "Default Account Expense",
        domain=[
            ('kind', '=', 'expense'),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    default_product_account_revenue = fields.Many2One(
        'account.account', "Default Account Revenue",
        domain=[
            ('kind', '=', 'revenue'),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    default_category_account_expense = fields.Many2One(
        'account.account', "Default Account Expense",
        domain=[
            ('kind', '=', 'expense'),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    default_category_account_revenue = fields.Many2One(
        'account.account', "Default Account Revenue",
        domain=[
            ('kind', '=', 'revenue'),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])


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
            table.column_rename(
                'default_account_category', 'default_accounts_category')

        super(ProductConfiguration, cls).__register__(module_name)

    @classmethod
    def default_default_accounts_category(cls):
        return False

    @classmethod
    def default_default_taxes_category(cls):
        return False
