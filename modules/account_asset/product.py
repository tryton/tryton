# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import PoolMeta
from trytond.modules.account_product import MissingFunction

__all__ = ['Category', 'Template']
__metaclass__ = PoolMeta


class Category:
    __name__ = 'product.category'
    account_depreciation = fields.Property(fields.Many2One('account.account',
            'Account Depreciation', domain=[
                ('kind', '=', 'other'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_parent')),
                }))
    account_depreciation_used = MissingFunction(
        fields.Many2One('account.account', 'Account Depreciation Used'),
        'missing_account', 'get_account')
    account_asset = fields.Property(fields.Many2One('account.account',
            'Account Asset',
            domain=[
                ('kind', '=', 'expense'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_parent')),
                }))
    account_asset_used = MissingFunction(
        fields.Many2One('account.account', 'Account Asset Used'),
        'missing_account', 'get_account')


class Template:
    __name__ = 'product.template'
    depreciable = fields.Boolean('Depreciable', states={
            'readonly': ~Eval('active', True),
            'invisible': Eval('type', '') != 'assets',
            }, depends=['active', 'type'])
    account_depreciation = fields.Property(fields.Many2One('account.account',
            'Account Depreciation', domain=[
                ('kind', '=', 'other'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'readonly': ~Eval('active', True),
                'required': ~Eval('account_category') & Eval('depreciable'),
                'invisible': (~Eval('depreciable')
                    | (Eval('type', '') != 'assets')
                    | ~Eval('context', {}).get('company')
                    | Eval('account_category')),
                },
            depends=['active', 'depreciable', 'type', 'account_category']))
    account_depreciation_used = MissingFunction(
        fields.Many2One('account.account', 'Account Depreciation Used'),
        'missing_account', 'get_account')
    account_asset = fields.Property(fields.Many2One('account.account',
            'Account Asset',
            domain=[
                ('kind', '=', 'expense'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'readonly': ~Eval('active', True),
                'required': ~Eval('account_category') & Eval('depreciable'),
                'invisible': (~Eval('depreciable')
                    | (Eval('type', '') != 'assets')
                    | ~Eval('context', {}).get('company')
                    | Eval('account_category')),
                },
            depends=['active', 'depreciable', 'type', 'account_category']))
    account_asset_used = MissingFunction(
        fields.Many2One('account.account', 'Account Asset Used'),
        'missing_account', 'get_account')
    depreciation_duration = fields.Property(fields.Numeric(
            'Depreciation Duration', digits=(16, 0),
            states={
                'readonly': ~Eval('active', True),
                'invisible': (~Eval('depreciable')
                    | (Eval('type', '') != 'assets')
                    | ~Eval('context', {}).get('company')),
                },
            depends=['active', 'depreciable', 'type'],
            help='In months'))
