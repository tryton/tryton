# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .purchase_request import *
from .purchase import *


def register():
    Pool.register(
        PurchaseRequest,
        HandlePurchaseCancellationExceptionStart,
        CreatePurchaseAskParty,
        Purchase,
        module='purchase_request', type_='model')
    Pool.register(
        CreatePurchase,
        HandlePurchaseCancellationException,
        module='purchase_request', type_='wizard')
