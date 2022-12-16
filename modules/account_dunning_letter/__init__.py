# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .dunning import *


def register():
    Pool.register(
        Level,
        module='account_dunning_letter', type_='model')
    Pool.register(
        ProcessDunning,
        module='account_dunning_letter', type_='wizard')
    Pool.register(
        Letter,
        module='account_dunning_letter', type_='report')
