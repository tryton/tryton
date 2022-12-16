# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, ValueMixin, fields
from trytond.pyson import Eval, Get
from trytond.pool import PoolMeta, Pool
from trytond.modules.company.model import CompanyValueMixin

__all__ = ['Configuration', 'ConfigurationStockJournal',
    'ConfigurationCostPriceCounterpartAccount',
    'FiscalYear', 'AccountMove']
stock_journal = fields.Many2One(
    'account.journal', "Stock Journal", required=True)


class Configuration(metaclass=PoolMeta):
    __name__ = 'account.configuration'
    stock_journal = fields.MultiValue(stock_journal)
    cost_price_counterpart_account = fields.MultiValue(fields.Many2One(
            'account.account', "Cost Price Counterpart Account",
            domain=[
                ('company', 'in', [Get(Eval('context', {}), 'company'), None]),
                ]))

    @classmethod
    def default_stock_journal(cls, **pattern):
        return cls.multivalue_model('stock_journal').default_stock_journal()


class ConfigurationStockJournal(ModelSQL, ValueMixin):
    "Account Configuration Stock Journal"
    __name__ = 'account.configuration.stock_journal'
    stock_journal = stock_journal

    @classmethod
    def default_stock_journal(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id('account', 'journal_stock')
        except KeyError:
            return None


class ConfigurationCostPriceCounterpartAccount(ModelSQL, CompanyValueMixin):
    "Account Configuration Cost Price Counterpart Account"
    __name__ = 'account.configuration.cost_price_counterpart_account'
    cost_price_counterpart_account = fields.Many2One(
        'account.account', "Cost Price Counterpart Account",
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])


class FiscalYear(metaclass=PoolMeta):
    __name__ = 'account.fiscalyear'
    account_stock_method = fields.Selection([
            (None, 'None'),
            ('continental', 'Continental'),
            ], 'Account Stock Method')


class AccountMove(metaclass=PoolMeta):
    __name__ = 'account.move'

    @classmethod
    def _get_origin(cls):
        return super(AccountMove, cls)._get_origin() + ['stock.move',
            'product.product', 'product.template']
