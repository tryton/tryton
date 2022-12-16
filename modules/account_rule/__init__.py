# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import account, party, product, purchase, sale, stock

__all__ = ['register']


def register():
    Pool.register(
        account.Configuration,
        account.AccountRule,
        party.Party,
        module='account_rule', type_='model')
    Pool.register(
        account.AccountRuleStock,
        module='account_rule', type_='model', depends=['stock'])
    Pool.register(
        product.Category,
        product.Template,
        module='account_rule', type_='model', depends=['product'])
    Pool.register(
        account.InvoiceLine,
        module='account_rule', type_='model', depends=['account_invoice'])
    Pool.register(
        account.InvoiceLineStock,
        module='account_rule', type_='model',
        depends=['account_invoice_stock'])
    Pool.register(
        purchase.Line,
        module='account_rule', type_='model', depends=['purchase'])
    Pool.register(
        sale.Line,
        module='account_rule', type_='model', depends=['sale'])
    Pool.register(
        stock.Move,
        module='account_rule', type_='model',
        depends=['stock'])
