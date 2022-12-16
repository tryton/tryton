# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from __future__ import unicode_literals

from trytond.pool import PoolMeta


__all__ = ['Move']


class Move:
    __metaclass__ = PoolMeta
    __name__ = 'account.move'

    @classmethod
    def _get_origin(cls):
        return super(Move, cls)._get_origin() + ['commission']
