# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import edocument

__all__ = ['register']


def register():
    Pool.register(
        edocument.Invoice,
        module='edocument_uncefact', type_='model')
