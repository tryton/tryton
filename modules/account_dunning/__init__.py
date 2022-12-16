# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .dunning import *
from .party import *
from .account import *


def register():
    Pool.register(
        Procedure,
        Level,
        Dunning,
        CreateDunningStart,
        ProcessDunningStart,
        Party,
        Configuration,
        MoveLine,
        module='account_dunning', type_='model')
    Pool.register(
        CreateDunning,
        ProcessDunning,
        module='account_dunning', type_='wizard')
