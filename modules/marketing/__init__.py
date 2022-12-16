# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

__all__ = ['register']


def register():
    Pool.register(
        module='marketing', type_='model')
    Pool.register(
        module='marketing', type_='wizard')
    Pool.register(
        module='marketing', type_='report')
