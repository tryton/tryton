# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import account, product, sale, stock

__all__ = ['register']


def register():
    Pool.register(
        account.Configuration,
        account.ConfigurationGiftCardAccount,
        account.AccountTypeTemplate,
        account.AccountType,
        account.InvoiceLine,
        product.Template,
        product.Product,
        sale.Configuration,
        sale.ConfigurationGiftCardSequence,
        sale.GiftCard,
        sale.Sale,
        sale.Line,
        stock.Move,
        module='sale_gift_card', type_='model')
    Pool.register(
        module='sale_gift_card', type_='wizard')
    Pool.register(
        sale.GiftCardReport,
        sale.GiftCardEmail,
        module='sale_gift_card', type_='report')
    Pool.register(
        sale.GiftCard_POS,
        sale.POSSale,
        sale.POSSaleLine,
        sale.POSPayGiftCard,
        module='sale_gift_card', type_='model', depends=['sale_point'])
    Pool.register(
        sale.POSPay,
        module='sale_gift_card', type_='wizard', depends=['sale_point'])
