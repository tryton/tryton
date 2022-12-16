# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .country import *


def register():
    Pool.register(
        Country,
        Subdivision,
        Zip,
        module='country', type_='model')
