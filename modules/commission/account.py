# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


class Journal(metaclass=PoolMeta):
    __name__ = 'account.journal'

    @classmethod
    def __setup__(cls):
        super(Journal, cls).__setup__()
        cls.type.selection.append(('commission', "Commission"))
