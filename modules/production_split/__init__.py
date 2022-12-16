# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from .production import *


def register():
    Pool.register(
        Production,
        SplitProductionStart,
        module='production_split', type_='model')
    Pool.register(
        SplitProduction,
        module='production_split', type_='wizard')
