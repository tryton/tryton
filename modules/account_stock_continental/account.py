#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval, Bool, Get
from trytond.pool import PoolMeta

__all__ = ['Configuration', 'AccountMove']
__metaclass__ = PoolMeta


class Configuration:
    __name__ = 'account.configuration'
    stock_journal = fields.Property(fields.Many2One(
            'account.journal', 'Stock Journal',
            states={
                'required': Bool(Eval('context', {}).get('company')),
                }))
    cost_price_counterpart_account = fields.Property(fields.Many2One(
            'account.account', 'Cost Price Counterpart Account', domain=[
                ('company', 'in', [Get(Eval('context', {}), 'company'), None]),
                ]))


class AccountMove:
    __name__ = 'account.move'

    @classmethod
    def _get_origin(cls):
        return super(AccountMove, cls)._get_origin() + ['stock.move',
            'product.product']
