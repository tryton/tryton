# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    chorus = fields.Boolean(
        "Chorus Pro",
        help="Send documents for this party through Chorus Pro")

    @classmethod
    def default_chorus(cls):
        return False
