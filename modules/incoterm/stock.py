# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.i18n import gettext
from trytond.model import ModelView, Workflow
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval

from .common import IncotermMixin
from .exceptions import DifferentIncotermWarning


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
        return Eval('supplier'), {'supplier'}


class ShipmentIn_Purchase(metaclass=PoolMeta):
    __name__ = 'stock.shipment.in'

    @classmethod
    @ModelView.button
    @Workflow.transition('received')
    def receive(cls, shipments):
        pool = Pool()
        Warning = pool.get('res.user.warning')
        PurchaseLine = pool.get('purchase.line')
        for shipment in shipments:
            if shipment.incoterm:
                incoterms = {
                    move.origin.purchase.incoterm for move in shipment.moves
                    if isinstance(move.origin, PurchaseLine)
                    and move.state != 'cancelled'}
                if {shipment.incoterm} != incoterms:
                    incoterms.discard(shipment.incoterm)
                    origin_incoterms = ', '.join(
                        i.rec_name if i else '' for i in incoterms)
                    warning_key = Warning.format(
                            'different_incoterm', [shipment])
                    if Warning.check(warning_key):
                        raise DifferentIncotermWarning(
                            warning_key,
                            gettext('incoterm'
                                '.msg_shipment_different_incoterm',
                                shipment_incoterm=shipment.incoterm.rec_name,
                                shipment=shipment.rec_name,
                                origin_incoterms=origin_incoterms))
        super().receive(shipments)


class ShipmentInReturn(ShipmentMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in.return'

    @classmethod
    def _incoterm_related_party(cls):
        return Eval('supplier'), {'supplier'}


class ShipmentOut(ShipmentMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    @classmethod
    def _incoterm_readonly_state(cls):
        return Eval('state').in_(['cancelled', 'shipped,' 'done'])

    @classmethod
    def _incoterm_related_party(cls):
        return Eval('customer'), {'customer'}


class ShipmentOut_Sale(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    @classmethod
    @ModelView.button
    @Workflow.transition('waiting')
    def wait(cls, shipments, moves=None):
        pool = Pool()
        Warning = pool.get('res.user.warning')
        SaleLine = pool.get('sale.line')
        for shipment in shipments:
            if shipment.incoterm:
                incoterms = {
                    move.origin.sale.incoterm for move in shipment.moves
                    if isinstance(move.origin, SaleLine)
                    and move.state != 'cancelled'}
                if {shipment.incoterm} != incoterms:
                    incoterms.discard(shipment.incoterm)
                    origin_incoterms = ', '.join(
                        i.rec_name if i else '' for i in incoterms)
                    warning_key = Warning.format(
                            'different_incoterm', [shipment])
                    if Warning.check(warning_key):
                        raise DifferentIncotermWarning(
                            warning_key,
                            gettext('incoterm'
                                '.msg_shipment_different_incoterm',
                                shipment_incoterm=shipment.incoterm.rec_name,
                                shipment=shipment.rec_name,
                                origin_incoterms=origin_incoterms))
        super().wait(shipments, moves)


class ShipmentOutReturn(ShipmentMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.return'

    @classmethod
    def _incoterm_related_party(cls):
        return Eval('customer'), {'customer'}
