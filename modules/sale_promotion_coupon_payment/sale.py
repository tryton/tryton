# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import PoolMeta


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    @fields.depends('party')
    def _coupon_parties(self):
        parties = super()._coupon_parties()
        if self.party:
            parties.update(self.party.payment_identical_parties)
        return parties
