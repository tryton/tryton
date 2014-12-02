# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import PoolMeta

from trytond.modules.account_product import MissingFunction

__all__ = ['Category', 'Template']
__metaclass__ = PoolMeta


class Category:
    __name__ = 'product.category'
    account_cogs = fields.Property(fields.Many2One('account.account',
            'Account Cost of Goods Sold', domain=[
                ('kind', '!=', 'view'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': (~Eval('context', {}, ).get('company')
                    | Eval('account_parent')),
                },
            depends=['account_parent']))
    account_cogs_used = MissingFunction(fields.Many2One('account.account',
            'Account Cost of Goods Sold Used'), 'missing_account',
        'get_account')


class Template:
    __name__ = 'product.template'
    account_cogs = fields.Property(fields.Many2One('account.account',
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
