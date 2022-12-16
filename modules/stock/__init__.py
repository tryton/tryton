# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import location
from . import shipment
from . import period
from . import move
from . import product
from . import inventory
from . import configuration
from . import party
from . import ir
from . import res
from . import stock_reporting_margin

from .move import StockMixin

__all__ = ['StockMixin', 'register']


def register():
    Pool.register(
        location.Location,
        location.WarehouseWasteLocation,
        location.Party,
        location.PartyLocation,
        location.ProductsByLocationsContext,
        location.ProductsByLocations,
        location.LocationLeadTime,
        move.Move,
        shipment.ShipmentIn,
        shipment.ShipmentInReturn,
        shipment.ShipmentOut,
        shipment.ShipmentOutReturn,
        shipment.ShipmentInternal,
        shipment.AssignPartial,
        party.Address,
        party.ContactMechanism,
        period.Period,
        period.Cache,
        product.Template,
        product.Product,
        product.ProductByLocationContext,
        product.ProductQuantitiesByWarehouse,
        product.ProductQuantitiesByWarehouseContext,
        product.ProductQuantitiesByWarehouseMove,
        product.RecomputeCostPriceStart,
        product.CostPriceRevision,
        product.ModifyCostPriceStart,
        inventory.Inventory,
        inventory.InventoryLine,
        inventory.CountSearch,
        inventory.CountQuantity,
        configuration.Configuration,
        configuration.ConfigurationSequence,
        configuration.ConfigurationLocation,
        ir.Cron,
        res.User,
        stock_reporting_margin.Context,
        stock_reporting_margin.Product,
        stock_reporting_margin.ProductTimeseries,
        stock_reporting_margin.Category,
        stock_reporting_margin.CategoryTimeseries,
        stock_reporting_margin.CategoryTree,
        module='stock', type_='model')
    Pool.register(
        shipment.Assign,
        product.OpenProductQuantitiesByWarehouse,
        product.OpenProductQuantitiesByWarehouseMove,
        product.RecomputeCostPrice,
        product.ModifyCostPrice,
        inventory.Count,
        party.Replace,
        party.Erase,
        module='stock', type_='wizard')
    Pool.register(
        shipment.DeliveryNote,
        shipment.PickingList,
        shipment.SupplierRestockingList,
        shipment.CustomerReturnRestockingList,
        shipment.InteralShipmentReport,
        module='stock', type_='report')
