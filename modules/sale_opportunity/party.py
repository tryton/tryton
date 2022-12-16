# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'
    _history = True


class Address(metaclass=PoolMeta):
    __name__ = 'party.address'
    _history = True


class Replace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super().fields_to_replace() + [
            ('sale.opportunity', 'party'),
            ]
