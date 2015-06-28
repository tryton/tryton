# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.model import fields
from trytond.pyson import Eval


__all__ = ['Configuration']


class Configuration:
    __metaclass__ = PoolMeta
    __name__ = 'account.configuration'

    default_product_account_expense = fields.Function(fields.Many2One(
            'account.account', 'Default Account Expense',
            domain=[
                ('kind', '=', 'expense'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ]),
        'get_account', setter='set_account')
    default_product_account_revenue = fields.Function(fields.Many2One(
            'account.account', 'Default Account Revenue',
            domain=[
                ('kind', '=', 'revenue'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ]),
        'get_account', setter='set_account')
    default_category_account_expense = fields.Function(fields.Many2One(
            'account.account', 'Default Account Expense',
            domain=[
                ('kind', '=', 'expense'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ]),
        'get_account', setter='set_account')
    default_category_account_revenue = fields.Function(fields.Many2One(
            'account.account', 'Default Account Revenue',
            domain=[
                ('kind', '=', 'revenue'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ]),
        'get_account', setter='set_account')

    @classmethod
    def _get_account_field(cls, name):
        pool = Pool()
        ModelField = pool.get('ir.model.field')
        if name in ['default_product_account_expense',
                'default_product_account_revenue']:
            field, = ModelField.search([
                    ('model.model', '=', 'product.template'),
                    ('name', '=', name[len('default_product_'):]),
                    ], limit=1)
            return field
        elif name in ['default_category_account_expense',
                'default_category_account_revenue']:
            field, = ModelField.search([
                    ('model.model', '=', 'product.category'),
                    ('name', '=', name[len('default_category_'):]),
                    ], limit=1)
            return field
        return super(Configuration, cls)._get_account_field(name)
