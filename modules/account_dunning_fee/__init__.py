# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import dunning
from . import account


def register():
    Pool.register(
        dunning.Fee,
        dunning.Level,
        dunning.Dunning,
        dunning.FeeDunningLevel,
        account.Move,
        module='account_dunning_fee', type_='model')
    Pool.register(
        dunning.Letter,
        module='account_dunning_fee', type_='report',
        depends=['account_dunning_letter'])
