# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .location import *
from .shipment import *
from .period import *
from .move import *
from .product import *
from . import inventory
from .configuration import *
from . import party


def register():
    Pool.register(
        Location,
        Party,
        PartyLocation,
        ProductsByLocationsContext,
        LocationLeadTime,
        Move,
        ShipmentIn,
        ShipmentInReturn,
        ShipmentOut,
        ShipmentOutReturn,
        AssignShipmentOutAssignFailed,
        ShipmentInternal,
        Address,
        AssignShipmentInternalAssignFailed,
        AssignShipmentInReturnAssignFailed,
        Period,
        Cache,
        Template,
        Product,
        ProductByLocationContext,
        ProductQuantitiesByWarehouse,
        ProductQuantitiesByWarehouseContext,
        inventory.Inventory,
        inventory.InventoryLine,
        inventory.CountSearch,
        inventory.CountQuantity,
        Configuration,
        ConfigurationSequence,
        ConfigurationLocation,
        module='stock', type_='model')
    Pool.register(
        AssignShipmentOut,
        AssignShipmentInternal,
        AssignShipmentInReturn,
        RecomputeCostPrice,
        inventory.Count,
        party.PartyReplace,
        party.PartyErase,
        module='stock', type_='wizard')
    Pool.register(
        DeliveryNote,
        PickingList,
        SupplierRestockingList,
        CustomerReturnRestockingList,
        InteralShipmentReport,
        module='stock', type_='report')
