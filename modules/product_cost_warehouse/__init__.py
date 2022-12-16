# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import account, company, ir, product, res, stock

__all__ = ['register']


def register():
    Pool.register(
        ir.Cron,
        ir.CronWarehouse,
        res.User,
        company.Company,
        product.Configuration,
        product.ConfigurationCostPriceWarehouse,
        product.Product,
        product.CostPrice,
        product.CostPriceRevision,
        stock.Configuration,
        stock.ConfigurationLocation,
        stock.Location,
        stock.Move,
        stock.ShipmentInternal,
        module='product_cost_warehouse', type_='model')
    Pool.register(
        account.InvoiceLine,
        module='product_cost_warehouse', type_='model',
        depends=['account_invoice_stock'])
    Pool.register(
        product.ProductCostHistory,
        module='product_cost_warehouse', type_='model',
        depends=['product_cost_history'])
    Pool.register(
        product.ModifyCostPrice,
        module='product_cost_warehouse', type_='wizard')
    Pool.register(
        module='product_cost_warehouse', type_='report')
