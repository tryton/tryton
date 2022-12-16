# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .sale import *
from .product import *
from .stock import *
from .configuration import *
from .invoice import *
from . import party
from . import sale_reporting


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
        ConfigurationSequence,
        ConfigurationSaleMethod,
        sale_reporting.Context,
        sale_reporting.Customer,
        sale_reporting.CustomerTimeseries,
        sale_reporting.Product,
        sale_reporting.ProductTimeseries,
        sale_reporting.Category,
        sale_reporting.CategoryTimeseries,
        sale_reporting.CategoryTree,
        sale_reporting.Country,
        sale_reporting.CountryTimeseries,
        sale_reporting.Subdivision,
        sale_reporting.SubdivisionTimeseries,
        sale_reporting.Region,
        Invoice,
        InvoiceLine,
        module='sale', type_='model')
    Pool.register(
        OpenCustomer,
        HandleShipmentException,
        HandleInvoiceException,
        ReturnSale,
        ModifyHeader,
        party.PartyReplace,
        party.PartyErase,
        sale_reporting.OpenRegion,
        module='sale', type_='wizard')
    Pool.register(
        SaleReport,
        module='sale', type_='report')
