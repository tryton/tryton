#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .order_point import *
from .product import *
from .purchase_request import *
from .shipment import *


def register():
    Pool.register(
        OrderPoint,
        Product,
        PurchaseRequest,
        CreatePurchaseRequestStart,
        CreatePurchaseAskTerm,
        CreatePurchaseAskParty,
        ShipmentInternal,
        module='stock_supply', type_='model')
    Pool.register(
        CreatePurchaseRequest,
        CreatePurchase,
        module='stock_supply', type_='wizard')
