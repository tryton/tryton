# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import user
from . import party


def register():
    Pool.register(
        user.User,
        user.UserAuthenticateAttempt,
        user.UserSession,
        module='web_user', type_='model')
    Pool.register(
        party.Replace,
        party.Erase,
        module='web_user', type_='wizard')
    Pool.register(
        user.EmailValidation,
        user.EmailResetPassword,
        module='web_user', type_='report')
