# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.model import fields
from trytond.pyson import Eval


class Configuration(metaclass=PoolMeta):
    __name__ = 'account.configuration'

    default_category_account_expense = fields.MultiValue(fields.Many2One(
            'account.account', 'Default Account Expense',
            domain=[
                ('type.expense', '=', True),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ]))
    default_category_account_revenue = fields.MultiValue(fields.Many2One(
            'account.account', 'Default Account Revenue',
            domain=[
                ('type.revenue', '=', True),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ]))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {'default_category_account_expense',
                'default_category_account_revenue'}:
            return pool.get('account.configuration.default_account')
        return super(Configuration, cls).multivalue_model(field)


class ConfigurationDefaultAccount(metaclass=PoolMeta):
    __name__ = 'account.configuration.default_account'
    default_category_account_expense = fields.Many2One(
        'account.account', "Default Account Expense",
        domain=[
            ('type.expense', '=', True),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    default_category_account_revenue = fields.Many2One(
        'account.account', "Default Account Revenue",
        domain=[
            ('type.revenue', '=', True),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
