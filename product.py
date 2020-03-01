# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import PoolMeta, Pool

from trytond.modules.account_product.product import (
    account_used, template_property)


class Category(metaclass=PoolMeta):
    __name__ = 'product.category'
    account_cogs = fields.MultiValue(fields.Many2One('account.account',
            'Account Cost of Goods Sold', domain=[
                ('closed', '!=', True),
                ('type.expense', '=', True),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': (~Eval('context', {}, ).get('company')
                    | Eval('account_parent')
                    | ~Eval('accounting', False)),
                },
            depends=['account_parent', 'accounting']))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'account_cogs':
            return pool.get('product.category.account')
        return super(Category, cls).multivalue_model(field)

    @property
    @account_used('account_cogs')
    def account_cogs_used(self):
        pass


class CategoryAccount(metaclass=PoolMeta):
    __name__ = 'product.category.account'
    account_cogs = fields.Many2One(
        'account.account', "Account Cost of Goods Sold",
        domain=[
            ('closed', '!=', True),
            ('type.expense', '=', True),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])

    @classmethod
    def __register__(cls, module_name):
        exist = backend.TableHandler.table_exist(cls._table)
        if exist:
            table = cls.__table_handler__(module_name)
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


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'

    @property
    @account_used('account_cogs', 'account_category')
    def account_cogs_used(self):
        pass


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'
    account_cogs_used = template_property('account_cogs_used')
