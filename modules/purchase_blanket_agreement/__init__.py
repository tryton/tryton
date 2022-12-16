# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import purchase

__all__ = ['register']


def register():
    Pool.register(
        purchase.Configuration,
        purchase.ConfigurationSequence,
        purchase.BlanketAgreement,
        purchase.BlanketAgreementLine,
        purchase.Purchase,
        purchase.Line,
        purchase.BlanketAgreementCreatePurchaseStart,
        module='purchase_blanket_agreement', type_='model')
    Pool.register(
        purchase.BlanketAgreementCreatePurchase,
        module='purchase_blanket_agreement', type_='wizard')
