# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import dunning


def register():
    Pool.register(
        dunning.Level,
        module='account_dunning_letter', type_='model')
    Pool.register(
        dunning.ProcessDunning,
        module='account_dunning_letter', type_='wizard')
    Pool.register(
        dunning.Letter,
        module='account_dunning_letter', type_='report')
