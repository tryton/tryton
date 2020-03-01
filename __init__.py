# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import sale
from . import product
from . import stock
from . import configuration
from . import invoice
from . import party
from . import sale_reporting


def register():
    Pool.register(
        stock.Move,
        sale.Sale,
        sale.SaleIgnoredInvoice,
        sale.SaleRecreatedInvoice,
        sale.SaleLine,
        sale.SaleLineTax,
        sale.SaleLineIgnoredMove,
        sale.SaleLineRecreatedMove,
        product.Template,
        product.Product,
        product.SaleContext,
        stock.ShipmentOut,
        stock.ShipmentOutReturn,
        sale.HandleShipmentExceptionAsk,
        sale.HandleInvoiceExceptionAsk,
        sale.ReturnSaleStart,
        configuration.Configuration,
        configuration.ConfigurationSequence,
        configuration.ConfigurationSaleMethod,
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
        invoice.Invoice,
        invoice.Line,
        module='sale', type_='model')
    Pool.register(
        sale.OpenCustomer,
        sale.HandleShipmentException,
        sale.HandleInvoiceException,
        sale.ReturnSale,
        sale.ModifyHeader,
        party.Replace,
        party.Erase,
        sale_reporting.OpenRegion,
        module='sale', type_='wizard')
    Pool.register(
        sale.SaleReport,
        module='sale', type_='report')
