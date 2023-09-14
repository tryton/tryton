# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import document

__all__ = ['register']


def register():
    Pool.register(
        document.IncomingOCRService,
        module='document_incoming_ocr_typless', type_='model')
