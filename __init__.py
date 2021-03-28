# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import incoterm
from . import company
from . import party
from . import carrier
from . import sale
from . import purchase
from . import stock
from . import account

__all__ = ['register']


def register():
    Pool.register(
        incoterm.Incoterm,
        incoterm.Incoterm_Company,
        company.Company,
        party.Party,
        party.Address,
        party.Incoterm,
        module='incoterm', type_='model')
    Pool.register(
        carrier.Carrier,
        module='incoterm', type_='model', depends=['carrier'])
    Pool.register(
        sale.Sale,
        module='incoterm', type_='model', depends=['sale'])
    Pool.register(
        sale.Sale_Carrier,
        module='incoterm', type_='model', depends=['sale_shipment_cost'])
    Pool.register(
        sale.Opportunity,
        module='incoterm', type_='model', depends=['sale_opportunity'])
    Pool.register(
        purchase.Purchase,
        module='incoterm', type_='model', depends=['purchase'])
    Pool.register(
        purchase.RequestQuotation,
        module='incoterm', type_='model',
        depends=['purchase_request_quotation'])
    Pool.register(
        purchase.RequestCreatePurchase,
        module='incoterm', type_='wizard',
        depends=['purchase_request_quotation'])
    Pool.register(
        stock.ShipmentIn,
        stock.ShipmentInReturn,
        stock.ShipmentOut,
        stock.ShipmentOutReturn,
        module='incoterm', type_='model', depends=['stock'])
    Pool.register(
        account.Invoice,
        account.InvoiceLine,
        module='incoterm', type_='model',
        depends=['account_invoice', 'account_invoice_stock'])
