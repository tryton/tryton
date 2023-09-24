# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import ir, purchase


def register():
    Pool.register(
        ir.Rule,
        purchase.PurchaseRequest,
        purchase.PurchaseRequisition,
        purchase.PurchaseRequisitionLine,
        purchase.Configuration,
        purchase.ConfigurationSequence,
        purchase.Purchase,
        module='purchase_requisition', type_='model')
    Pool.register(
        purchase.HandlePurchaseCancellationException,
        purchase.CreatePurchase,
        module='purchase_requisition', type_='wizard')
