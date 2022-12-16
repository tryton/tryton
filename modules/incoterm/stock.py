# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta
from trytond.pyson import Eval

from .common import IncotermMixin


class ShipmentMixin(IncotermMixin):

    @property
    def shipping_to(self):
        party = super().shipping_to
        if self.incoterm and self.incoterm_location:
            party = self.incoterm_location.party
        return party

    @property
    def shipping_to_address(self):
        address = super().shipping_to_address
        if self.incoterm and self.incoterm_location:
            address = self.incoterm_location
        return address


class ShipmentIn(ShipmentMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in'

    @classmethod
    def _incoterm_related_party(cls):
        return Eval('supplier'), ['supplier']


class ShipmentInReturn(ShipmentMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in.return'

    @classmethod
    def _incoterm_related_party(cls):
        return Eval('supplier'), ['supplier']


class ShipmentOut(ShipmentMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    @classmethod
    def _incoterm_related_party(cls):
        return Eval('customer'), ['customer']


class ShipmentOutReturn(ShipmentMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.return'

    @classmethod
    def _incoterm_related_party(cls):
        return Eval('customer'), ['customer']
