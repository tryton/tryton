# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import purchase
from . import product
from . import stock
from . import configuration
from . import invoice
from . import party


def register():
    Pool.register(
        stock.Move,
        purchase.Purchase,
        purchase.PurchaseIgnoredInvoice,
        purchase.PurchaseRecreatedInvoice,
        purchase.Line,
        purchase.LineTax,
        purchase.LineIgnoredMove,
        purchase.LineRecreatedMove,
        product.Template,
        product.Product,
        product.ProductSupplier,
        product.ProductSupplierPrice,
        stock.ShipmentIn,
        stock.ShipmentInReturn,
        purchase.HandleShipmentExceptionAsk,
        purchase.HandleInvoiceExceptionAsk,
        configuration.Configuration,
        configuration.ConfigurationSequence,
        configuration.ConfigurationPurchaseMethod,
        invoice.Invoice,
        invoice.InvoiceLine,
        stock.Location,
        party.Party,
        party.CustomerCode,
        purchase.ReturnPurchaseStart,
        module='purchase', type_='model')
    Pool.register(
        purchase.PurchaseReport,
        module='purchase', type_='report')
    Pool.register(
        purchase.OpenSupplier,
        purchase.HandleShipmentException,
        purchase.HandleInvoiceException,
        party.PartyReplace,
        party.PartyErase,
        purchase.ModifyHeader,
        purchase.ReturnPurchase,
        module='purchase', type_='wizard')
