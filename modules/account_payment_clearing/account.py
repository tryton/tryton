# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


__all__ = ['Move']
__metaclass__ = PoolMeta


class Move:
    __name__ = 'account.move'

    @classmethod
    def _get_origin(cls):
        models = super(Move, cls)._get_origin()
        return models + ['account.payment']
