# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import account, document

__all__ = ['register']


def register():
    Pool.register(
        document.Incoming,
        document.IncomingOCRService,
        module='document_incoming_ocr', type_='model')
    Pool.register(
        account.Invoice,
        document.IncomingSupplierInvoice,
        module='document_incoming_ocr', type_='model',
        depends=[
            'account_invoice', 'account_product', 'document_incoming_invoice',
            'product'])
    Pool.register(
        document.IncomingSupplierInvoicePurchase,
        module='document_incoming_ocr', type_='model',
        depends=['purchase'])
