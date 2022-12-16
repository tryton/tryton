# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import account
from . import product
from . import sale
from . import stock

__all__ = ['register']


def register():
    Pool.register(
        account.InvoiceLine,
        product.Template,
        product.Product,
        sale.Line,
        stock.Move,
        module='sale_secondary_unit', type_='model')
    Pool.register(
        product.ProductCustomer,
        sale.Line_ProductCustomer,
        module='sale_secondary_unit', type_='model',
        depends=['sale_product_customer'])
    Pool.register(
        sale.OpportunityLine,
        module='sale_secondary_unit', type_='model',
        depends=['sale_opportunity'])
