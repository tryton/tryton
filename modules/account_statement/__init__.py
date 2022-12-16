#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .journal import *
from .statement import *
from .account import *


def register():
    Pool.register(
        Journal,
        Statement,
        Line,
        Move,
        module='account_statement', type_='model')
