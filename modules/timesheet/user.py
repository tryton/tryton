# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


class UserApplication(metaclass=PoolMeta):
    __name__ = 'res.user.application'

    @classmethod
    def __setup__(cls):
        super(UserApplication, cls).__setup__()
        cls.application.selection.append(('timesheet', 'Timesheet'))
