# This file is part purchase_request_for_quotation module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool
from . import purchase

__all__ = ['register']


def register():
    Pool.register(
        purchase.Configuration,
        purchase.ConfigurationSequence,
        purchase.Quotation,
        purchase.QuotationLine,
        purchase.CreatePurchaseRequestQuotationAskSuppliers,
        purchase.CreatePurchaseRequestQuotationSucceed,
        purchase.PurchaseRequest,
        module='purchase_request_quotation', type_='model')
    Pool.register(
        purchase.PurchaseRequestQuotationReport,
        module='purchase_request_quotation', type_='report')
    Pool.register(
        purchase.CreatePurchaseRequestQuotation,
        purchase.CreatePurchase,
        module='purchase_request_quotation', type_='wizard')
