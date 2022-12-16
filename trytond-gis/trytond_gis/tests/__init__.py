# This file is part of trytond_gis.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import gis


def register(name):
    Pool.register(
        gis.Point,
        module=name, type_='model')
