# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.modules.sale.sale_reporting import Abstract
from trytond.pool import Pool

from . import account, product, sale, sale_reporting, stock


def register():
    Pool.register(
        sale.POS,
        sale.POSSale,
        sale.POSSaleLine,
        sale.POSCashSession,
        sale.POSCashSessionRelation,
        sale.POSPayment,
        sale.POSPaymentMethod,
        sale.POSCashTransfer,
        sale.POSCashTransferType,
        product.Template,
        product.Product,
        product.GrossPrice,
        stock.Move,
        account.Move,
        account.MoveLine,
        module='sale_point', type_='model')
    Pool.register(
        sale.POSPay,
        module='sale_point', type_='wizard')
    Pool.register_mixin(sale_reporting.AbstractMixin, Abstract, 'sale_point')
