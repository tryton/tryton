#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import PoolMeta

__all__ = ['Category', 'Template']
__metaclass__ = PoolMeta


class Category:
    __name__ = 'product.category'
    account_cogs = fields.Property(fields.Many2One('account.account',
            'Account Cost of Goods Sold', domain=[
                ('kind', '!=', 'view'),
                ('company', '=', Eval('context', {}).get('company', 0)),
                ],
            states={
                'invisible': (~Eval('context', {}, ).get('company')
                    | Eval('account_parent')),
                },
            depends=['account_parent']))
    account_cogs_used = fields.Function(fields.Many2One('account.account',
        'Account Cost of Goods Sold Used'), 'get_account')


class Template:
    __name__ = 'product.template'
    account_cogs = fields.Property(fields.Many2One('account.account',
            'Account Cost of Goods Sold', domain=[
                ('kind', '!=', 'view'),
                ('company', '=', Eval('context', {}).get('company', 0)),
                ],
            states={
                'invisible': ((~Eval('context', {}).get('company'))
                    | Eval('account_category')
                    | (Eval('type') != 'goods')),
                'required': ((Eval('type') == 'goods')
                    & Eval('context', {}).get('company')
                    & ~Eval('account_category')),
                },
            help='This account will be used instead of the one defined '
            'on the category.',
            depends=['account_category', 'type']))
    account_cogs_used = fields.Function(fields.Many2One('account.account',
        'Account Cost of Goods Sold Used'), 'get_account')
