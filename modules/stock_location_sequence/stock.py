# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import sequence_ordered
from trytond.pyson import Eval, Bool
from trytond.pool import PoolMeta

__all__ = ['Location']


class Location(sequence_ordered(), metaclass=PoolMeta):
    "Stock Location"
    __name__ = 'stock.location'

    @classmethod
    def __setup__(cls):
        super(Location, cls).__setup__()
        previous_readonly = cls.sequence.states.get('readonly', Bool(False))
        cls.sequence.states['readonly'] = previous_readonly | ~Eval('active')
        cls.sequence.depends = ['active']
