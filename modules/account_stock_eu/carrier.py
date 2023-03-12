# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import PoolMeta


class Carrier(metaclass=PoolMeta):
    __name__ = 'carrier'

    intrastat_transport = fields.Many2One(
        'account.stock.eu.intrastat.transport', "Intrastat Transport")
