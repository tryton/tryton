#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Not, Eval, Bool, Or, In, And


class Category(ModelSQL, ModelView):
    _name = 'product.category'

    account_cogs = fields.Property(fields.Many2One('account.account',
        'Account Cost of Goods Sold', domain=[
            ('kind', '!=', 'view'),
            ('company', '=', Eval('company')),
        ],
        states={
            'invisible': Not(Bool(Eval('company'))),
        }))

Category()


class Template(ModelSQL, ModelView):
    _name = 'product.template'

    account_cogs = fields.Property(fields.Many2One('account.account',
        'Account Cost of Good Sold', domain=[
            ('kind', '!=', 'view'),
            ('company', '=', Eval('company')),
        ],
        states={
            'invisible': Or(Not(Bool(Eval('company'))),
                Bool(Eval('account_category'))),
            'required': And(In(Eval('type'), ['stockable', 'consumable']),
                Bool(Eval('company')),
                Not(Bool(Eval('account_category')))),
        }, help='This account will be used instead of the one defined '
        'on the category.', depends=['account_category']))
    account_cogs_used = fields.Function(fields.Many2One('account.account',
        'Account Cost of Goods Sold Used'), 'get_account')

Template()
