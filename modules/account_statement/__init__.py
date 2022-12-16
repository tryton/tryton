# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .journal import *
from .statement import *
from .account import *
from .party import PartyReplace


def register():
    Pool.register(
        Journal,
        Statement,
        Line,
        LineGroup,
        Move,
        Origin,
        OriginInformation,
        ImportStatementStart,
        module='account_statement', type_='model')
    Pool.register(
        PartyReplace,
        ImportStatement,
        ReconcileStatement,
        module='account_statement', type_='wizard')
    Pool.register(
        StatementReport,
        module='account_statement', type_='report')
