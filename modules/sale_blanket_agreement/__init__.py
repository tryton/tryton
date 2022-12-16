# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import sale

__all__ = ['register']


def register():
    Pool.register(
        sale.Configuration,
        sale.ConfigurationSequence,
        sale.BlanketAgreement,
        sale.BlanketAgreementLine,
        sale.Sale,
        sale.Line,
        sale.BlanketAgreementCreateSaleStart,
        module='sale_blanket_agreement', type_='model')
    Pool.register(
        sale.BlanketAgreementCreateSale,
        module='sale_blanket_agreement', type_='wizard')
