# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .sale import *
from .product import *
from .stock import *
from .configuration import *
from .invoice import *


def register():
    Pool.register(
        Move,
        Sale,
        SaleIgnoredInvoice,
        SaleRecreatedInvoice,
        SaleLine,
        SaleLineTax,
        SaleLineIgnoredMove,
        SaleLineRecreatedMove,
        Template,
        Product,
        ShipmentOut,
        ShipmentOutReturn,
        HandleShipmentExceptionAsk,
        HandleInvoiceExceptionAsk,
        ReturnSaleStart,
        Configuration,
        Invoice,
        InvoiceLine,
        module='sale', type_='model')
    Pool.register(
        OpenCustomer,
        HandleShipmentException,
        HandleInvoiceException,
        ReturnSale,
        module='sale', type_='wizard')
    Pool.register(
        SaleReport,
        module='sale', type_='report')
