# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import (
    account, account_stock_eu, carrier, company, country, customs, stock)

__all__ = ['register']


def register():
    Pool.register(
        country.Country,
        country.Subdivision,
        company.Company,
        account.FiscalYear,
        account_stock_eu.IntrastatTransaction,
        account_stock_eu.IntrastatTransport,
        account_stock_eu.IntrastatDeclaration,
        account_stock_eu.IntrastatDeclarationContext,
        account_stock_eu.IntrastatDeclarationLine,
        account_stock_eu.IntrastatDeclarationExportResult,
        customs.TariffCode,
        stock.Move,
        stock.ShipmentIn,
        stock.ShipmentInReturn,
        stock.ShipmentOut,
        stock.ShipmentOutReturn,
        stock.ShipmentInternal,
        module='account_stock_eu', type_='model')
    Pool.register(
        stock.Move_Production,
        module='account_stock_eu', type_='model',
        depends=['production'])
    Pool.register(
        account_stock_eu.IntrastatDeclarationLine_Incoterm,
        stock.Move_Incoterm,
        module='account_stock_eu', type_='model',
        depends=['incoterm'])
    Pool.register(
        stock.Move_Consignment,
        module='account_stock_eu', type_='model',
        depends=['stock_consignment'])
    Pool.register(
        stock.ShipmentDrop,
        module='account_stock_eu', type_='model',
        depends=['sale_supply_drop_shipment'])
    Pool.register(
        carrier.Carrier,
        module='account_stock_eu', type_='model',
        depends=['carrier', 'incoterm'])
    Pool.register(
        account_stock_eu.IntrastatDeclarationExport,
        account_stock_eu.IntrastatDeclarationExport_BE,
        account_stock_eu.IntrastatDeclarationExport_ES,
        module='account_stock_eu', type_='wizard')
    Pool.register(
        account_stock_eu.IntrastatDeclarationExport_Incoterm,
        account_stock_eu.IntrastatDeclarationExport_BE_Incoterm,
        account_stock_eu.IntrastatDeclarationExport_ES_Incoterm,
        module='account_stock_eu', type_='wizard',
        depends=['incoterm'])
