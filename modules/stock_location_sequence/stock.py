# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import sequence_ordered
from trytond.pool import PoolMeta


class Location(sequence_ordered(), metaclass=PoolMeta):
    __name__ = 'stock.location'
