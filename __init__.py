# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import party
from . import sale
from . import configuration


def register():
    Pool.register(
        sale.Sale,
        party.Party,
        party.PartySaleInvoiceGroupingMethod,
        configuration.Configuration,
        configuration.ConfigurationSaleMethod,
        module='sale_invoice_grouping', type_='model')
