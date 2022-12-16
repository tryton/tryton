# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .dunning import *
from .account import *


def register():
    Pool.register(
        Fee,
        Level,
        Dunning,
        FeeDunningLevel,
        Move,
        module='account_dunning_fee', type_='model')
    Pool.register(
        Letter,
        module='account_dunning_fee', type_='report')
