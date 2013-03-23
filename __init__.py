#This file is part of Tryton.  The COPYRIGHT file at the top level of this
#repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .location import *
from .shipment import *
from .period import *
from .move import *
from .product import *
from .inventory import *
from .configuration import *


def register():
    Pool.register(
        Location,
        Party,
        ProductsByLocationsStart,
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
        ProductByLocationStart,
        ProductQuantitiesByWarehouse,
        ProductQuantitiesByWarehouseStart,
        Inventory,
        InventoryLine,
        Configuration,
        module='stock', type_='model')
    Pool.register(
        ProductsByLocations,
        AssignShipmentOut,
        AssignShipmentInternal,
        AssignShipmentInReturn,
        CreateShipmentOutReturn,
        ProductByLocation,
        OpenProductQuantitiesByWarehouse,
        module='stock', type_='wizard')
    Pool.register(
        DeliveryNote,
        PickingList,
        SupplierRestockingList,
        CustomerReturnRestockingList,
        InteralShipmentReport,
        module='stock', type_='report')
