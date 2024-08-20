# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import PoolMeta


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    cost_sale_shipment_carriages = fields.One2Many(
        'stock.shipment.carriage', 'cost_sale_invoice_line',
        "Cost Sale of Shipment Carriages", readonly=True)
