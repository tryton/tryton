# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import payment
from . import account
from . import statement


def register():
    Pool.register(
        payment.Journal,
        payment.Payment,
        payment.SucceedStart,
        account.Move,
        module='account_payment_clearing', type_='model')
    Pool.register(
        statement.Statement,
        statement.StatementLine,
        module='account_payment_clearing', type_='model',
        depends=['account_statement'])
    Pool.register(
        payment.Succeed,
        module='account_payment_clearing', type_='wizard')
