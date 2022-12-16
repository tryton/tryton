# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import user
from . import party
from . import ir


def register():
    Pool.register(
        user.User,
        user.User_PartySecondary,
        user.UserAuthenticateAttempt,
        user.UserSession,
        ir.Email,
        ir.EmailTemplate,
        module='web_user', type_='model')
    Pool.register(
        party.Replace,
        party.Erase,
        module='web_user', type_='wizard')
    Pool.register(
        user.EmailValidation,
        user.EmailResetPassword,
        module='web_user', type_='report')
