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

from .move import StockMixin

__all__ = ['StockMixin', 'register']


def register():
    Pool.register(
        location.Location,
        location.Party,
        location.PartyLocation,
        location.ProductsByLocationsContext,
        location.LocationLeadTime,
        move.Move,
        shipment.ShipmentIn,
        shipment.ShipmentInReturn,
        shipment.ShipmentOut,
        shipment.ShipmentOutReturn,
        shipment.AssignShipmentOutAssignFailed,
        shipment.ShipmentInternal,
        shipment.Address,
        shipment.AssignShipmentInternalAssignFailed,
        shipment.AssignShipmentInReturnAssignFailed,
        period.Period,
        period.Cache,
        product.Template,
        product.Product,
        product.ProductByLocationContext,
        product.ProductQuantitiesByWarehouse,
        product.ProductQuantitiesByWarehouseContext,
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
        module='stock', type_='model')
    Pool.register(
        shipment.AssignShipmentOut,
        shipment.AssignShipmentInternal,
        shipment.AssignShipmentInReturn,
        product.OpenProductQuantitiesByWarehouse,
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
