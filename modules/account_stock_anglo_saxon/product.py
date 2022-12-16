# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import PoolMeta, Pool

from trytond.modules.account_product import MissingFunction

__all__ = ['Category', 'CategoryAccount', 'Template', 'TemplateAccount',
    'Product']


class Category:
    __metaclass__ = PoolMeta
    __name__ = 'product.category'
    account_cogs = fields.MultiValue(fields.Many2One('account.account',
            'Account Cost of Goods Sold', domain=[
                ('kind', '!=', 'view'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': (~Eval('context', {}, ).get('company')
                    | Eval('account_parent')
                    | ~Eval('accounting', False)),
                },
            depends=['account_parent', 'accounting']))
    account_cogs_used = MissingFunction(fields.Many2One('account.account',
            'Account Cost of Goods Sold Used'), 'missing_account',
        'get_account')

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'account_cogs':
            return pool.get('product.category.account')
        return super(Category, cls).multivalue_model(field)


class CategoryAccount:
    __metaclass__ = PoolMeta
    __name__ = 'product.category.account'
    account_cogs = fields.Many2One(
        'account.account', "Account Cost of Goods Sold",
        domain=[
            ('kind', '!=', 'view'),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        exist = TableHandler.table_exist(cls._table)
        if exist:
            table = TableHandler(cls, module_name)
            exist &= table.column_exist('account_cogs')

        super(CategoryAccount, cls).__register__(module_name)

        if not exist:
            # Re-migration
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('account_cogs')
        value_names.append('account_cogs')
        super(CategoryAccount, cls)._migrate_property(
            field_names, value_names, fields)


class Template:
    __metaclass__ = PoolMeta
    __name__ = 'product.template'
    account_cogs = fields.MultiValue(fields.Many2One('account.account',
            'Account Cost of Goods Sold', domain=[
                ('kind', '!=', 'view'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': ((~Eval('context', {}).get('company'))
                    | Eval('account_category')
                    | (Eval('type') != 'goods')),
                },
            help='This account will be used instead of the one defined '
            'on the category.',
            depends=['account_category', 'type']))
    account_cogs_used = MissingFunction(fields.Many2One('account.account',
            'Account Cost of Goods Sold Used'), 'missing_account',
        'get_account')

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'account_cogs':
            return pool.get('product.template.account')
        return super(Template, cls).multivalue_model(field)


class TemplateAccount:
    __metaclass__ = PoolMeta
    __name__ = 'product.template.account'
    account_cogs = fields.Many2One(
        'account.account', "Account Cost of Goods Sold",
        domain=[
            ('kind', '!=', 'view'),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        exist = TableHandler.table_exist(cls._table)
        if exist:
            table = TableHandler(cls, module_name)
            exist &= table.column_exist('account_cogs')

        super(TemplateAccount, cls).__register__(module_name)

        if not exist:
            # Re-migration
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('account_cogs')
        value_names.append('account_cogs')
        super(TemplateAccount, cls)._migrate_property(
            field_names, value_names, fields)


class Product:
    __metaclass__ = PoolMeta
    __name__ = 'product.product'
    # Avoid raise of UserError from MissingFunction
    account_cogs_used = fields.Function(
        fields.Many2One('account.account', 'Account Cost of Goods Sold Used'),
        'get_template')
