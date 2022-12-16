#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval


class Category(ModelSQL, ModelView):
    _name = 'product.category'

    account_stock = fields.Property(fields.Many2One('account.account',
            'Account Stock', domain=[
                ('kind', '=', 'stock'),
                ('company', '=', Eval('context', {}).get('company', 0)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_parent')),
                },
            depends=['account_parent']))
    account_stock_supplier = fields.Property(fields.Many2One('account.account',
            'Account Stock Supplier', domain=[
                ('kind', '=', 'stock'),
                ('company', '=', Eval('context', {}).get('company', 0)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_parent')),
                },
            depends=['account_parent']))
    account_stock_customer = fields.Property(fields.Many2One('account.account',
            'Account Stock Customer', domain=[
                ('kind', '=', 'stock'),
                ('company', '=', Eval('context', {}).get('company', 0)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_parent')),
                },
            depends=['account_parent']))
    account_stock_lost_found = fields.Property(fields.Many2One(
            'account.account', 'Account Stock Lost and Found', domain=[
                ('kind', '=', 'stock'),
                ('company', '=', Eval('context', {}).get('company', 0)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_parent')),
                },
            depends=['account_parent']))
    account_stock_used = fields.Function(fields.Many2One('account.account',
        'Account Stock Used'), 'get_account')
    account_stock_supplier_used = fields.Function(fields.Many2One(
        'account.account', 'Account Stock Supplier Used'), 'get_account')
    account_stock_customer_used = fields.Function(fields.Many2One(
        'account.account', 'Account Stock Customer Used'), 'get_account')
    account_stock_lost_found_used = fields.Function(fields.Many2One(
        'account.account', 'Account Stock Lost and Found'), 'get_account')

Category()


class Template(ModelSQL, ModelView):
    _name = 'product.template'

    account_stock = fields.Property(fields.Many2One('account.account',
            'Account Stock',
            domain=[
                ('kind', '=', 'stock'),
                ('company', '=', Eval('context', {}).get('company', 0)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_category')),
                'required': ((Eval('type') == 'goods')
                    & Eval('context', {}).get('company')
                    & ~Eval('account_category')),
                }, help='This account will be used instead of the one defined '
            'on the category.',
            depends=['account_category', 'type']))
    account_stock_supplier = fields.Property(fields.Many2One('account.account',
            'Account Stock Supplier',
            domain=[
                ('kind', '=', 'stock'),
                ('company', '=', Eval('context', {}).get('company', 0)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_category')),
                'required': ((Eval('type') == 'goods')
                    & Eval('context', {}).get('company')
                    & ~Eval('account_category')),
                }, help='This account will be used instead of the one defined '
            'on the category.',
            depends=['account_category', 'type']))
    account_stock_customer = fields.Property(fields.Many2One('account.account',
            'Account Stock Customer',
            domain=[
                ('kind', '=', 'stock'),
                ('company', '=', Eval('context', {}).get('company', 0)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_category')),
                'required': ((Eval('type') == 'goods')
                    & Eval('context', {}).get('company')
                    & ~Eval('account_category')),
                }, help='This account will be used instead of the one defined '
            'on the category.',
            depends=['account_category', 'type']))
    account_stock_lost_found = fields.Property(fields.Many2One(
            'account.account', 'Account Stock Lost and Found',
            domain=[
                ('kind', '=', 'stock'),
                ('company', '=', Eval('context', {}).get('company', 0)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_category')),
                'required': ((Eval('type') == 'goods')
                    & Eval('context', {}).get('company')
                    & ~Eval('account_category')),
                }, help='This account will be used instead of the one defined '
            'on the category.',
            depends=['account_category', 'type']))
    account_stock_used = fields.Function(fields.Many2One('account.account',
        'Account Stock Used'), 'get_account')
    account_stock_supplier_used = fields.Function(fields.Many2One(
        'account.account', 'Account Stock Supplier Used'), 'get_account')
    account_stock_customer_used = fields.Function(fields.Many2One(
        'account.account', 'Account Stock Customer Used'), 'get_account')
    account_stock_lost_found_used = fields.Function(fields.Many2One(
        'account.account', 'Account Stock Lost and Found'), 'get_account')

Template()
