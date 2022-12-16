# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import party, sale

__all__ = ['register']


def register():
    Pool.register(
        sale.InvoiceTerm,
        sale.InvoiceTermRelativeDelta,
        sale.Configuration,
        sale.ConfigurationSaleMethod,
        sale.Sale,
        party.Party,
        party.PartySaleMethod,
        module='sale_invoice_date', type_='model')
