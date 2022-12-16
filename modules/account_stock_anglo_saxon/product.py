#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval


class Category(ModelSQL, ModelView):
    _name = 'product.category'

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

Category()


class Template(ModelSQL, ModelView):
    _name = 'product.template'

    account_cogs = fields.Property(fields.Many2One('account.account',
            'Account Cost of Goods Sold', domain=[
                ('kind', '!=', 'view'),
                ('company', '=', Eval('context', {}).get('company', 0)),
                ],
            states={
                'invisible': ((~Eval('context', {}).get('company'))
                    | Eval('account_category')),
                'required': ((Eval('type') == 'goods')
                    & Eval('context', {}).get('company')
                    & ~Eval('account_category')),
                },
            help='This account will be used instead of the one defined '
            'on the category.',
            depends=['account_category', 'type']))
    account_cogs_used = fields.Function(fields.Many2One('account.account',
        'Account Cost of Goods Sold Used'), 'get_account')

Template()
