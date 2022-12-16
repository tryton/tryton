# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .user import *
from . import party


def register():
    Pool.register(
        User,
        UserAuthenticateAttempt,
        UserSession,
        module='web_user', type_='model')
    Pool.register(
        party.PartyReplace,
        party.PartyErase,
        module='web_user', type_='wizard')
    Pool.register(
        EmailValidation,
        EmailResetPassword,
        module='web_user', type_='report')
