# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import journal
from . import statement
from . import account
from . import party


def register():
    Pool.register(
        journal.Journal,
        statement.Statement,
        statement.Line,
        statement.LineGroup,
        account.Journal,
        account.Move,
        account.MoveLine,
        statement.Origin,
        statement.OriginInformation,
        statement.ImportStatementStart,
        module='account_statement', type_='model')
    Pool.register(
        party.Replace,
        statement.ImportStatement,
        statement.ReconcileStatement,
        module='account_statement', type_='wizard')
    Pool.register(
        statement.StatementReport,
        module='account_statement', type_='report')
