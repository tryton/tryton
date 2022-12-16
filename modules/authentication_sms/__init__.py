# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import res


def register():
    Pool.register(
        res.User,
        res.UserLoginSMSCode,
        module='authentication_sms', type_='model')
