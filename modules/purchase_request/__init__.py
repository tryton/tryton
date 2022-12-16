# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import purchase_request
from . import purchase
from . import party


def register():
    Pool.register(
        purchase_request.PurchaseRequest,
        purchase_request.HandlePurchaseCancellationExceptionStart,
        purchase_request.CreatePurchaseAskParty,
        purchase.Purchase,
        purchase.Line,
        module='purchase_request', type_='model')
    Pool.register(
        purchase_request.CreatePurchase,
        purchase_request.HandlePurchaseCancellationException,
        party.Replace,
        module='purchase_request', type_='wizard')
