# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .party import *
from .sale import *
from . import configuration


def register():
    Pool.register(
        Sale,
        Party,
        PartySaleInvoiceGroupingMethod,
        configuration.Configuration,
        configuration.ConfigurationSaleMethod,
        module='sale_invoice_grouping', type_='model')
