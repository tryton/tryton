# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import invoice
from . import asset


def register():
    Pool.register(
        invoice.InvoiceLine,
        invoice.AnalyticAccountEntry,
        module='analytic_invoice', type_='model')
    Pool.register(
        asset.Asset,
        module='analytic_invoice', type_='model',
        depends=['account_asset'])
