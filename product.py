# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import PoolMeta, Pool
from trytond.modules.account_product.product import (
    account_used, template_property)


class Category(metaclass=PoolMeta):
    __name__ = 'product.category'
    account_depreciation = fields.MultiValue(fields.Many2One('account.account',
            'Account Depreciation', domain=[
                ('type.fixed_asset', '=', True),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_parent')
                    | ~Eval('accounting', False)),
                },
            depends=['account_parent', 'accounting']))
    account_asset = fields.MultiValue(fields.Many2One('account.account',
            'Account Asset',
            domain=[
                ('type.fixed_asset', '=', True),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_parent')
                    | ~Eval('accounting', False)),
                },
            depends=['account_parent', 'accounting']))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {'account_depreciation', 'account_asset'}:
            return pool.get('product.category.account')
        return super(Category, cls).multivalue_model(field)

    @property
    @account_used('account_depreciation')
    def account_depreciation_used(self):
        pass

    @property
    @account_used('account_asset')
    def account_asset_used(self):
        pass


class CategoryAccount(metaclass=PoolMeta):
    __name__ = 'product.category.account'
    account_depreciation = fields.Many2One(
        'account.account', "Account Depreciation",
        domain=[
            ('type.fixed_asset', '=', True),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    account_asset = fields.Many2One(
        'account.account', "Account Asset",
        domain=[
            ('type.fixed_asset', '=', True),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])

    @classmethod
    def __register__(cls, module_name):
        exist = backend.TableHandler.table_exist(cls._table)
        if exist:
            table = cls.__table_handler__(module_name)
            exist &= (table.column_exist('account_depreciation')
                and table.column_exist('account_asset'))

        super(CategoryAccount, cls).__register__(module_name)

        if not exist:
            # Re-migration
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.extend(['account_depreciation', 'account_asset'])
        value_names.extend(['account_depreciation', 'account_asset'])
        super(CategoryAccount, cls)._migrate_property(
            field_names, value_names, fields)


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'
    depreciable = fields.Boolean('Depreciable', states={
            'invisible': Eval('type', '') != 'assets',
            }, depends=['type'])
    depreciation_duration = fields.Integer(
        "Depreciation Duration",
        states={
            'invisible': (~Eval('depreciable')
                | (Eval('type', '') != 'assets')),
            },
        depends=['depreciable', 'type'],
        help='In months')

    @property
    @account_used('account_depreciation', 'account_category')
    def account_depreciation_used(self):
        pass

    @property
    @account_used('account_asset', 'account_category')
    def account_asset_used(self):
        pass


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    account_depreciation_used = template_property('account_depreciation_used')
    account_asset_used = template_property('account_asset_used')
