# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.pool import PoolMeta, Pool
from trytond.model import ModelSQL, ModelView, fields

from trytond.modules.product import round_price

from .product import ComponentMixin
from .common import order_mixin, order_line_mixin, order_line_component_mixin
from .common import get_shipments_returns, search_shipments_returns
from .common import handle_shipment_exception_mixin
from .common import AmendmentLineMixin


class Purchase(order_mixin('purchase'), metaclass=PoolMeta):
    __name__ = 'purchase.purchase'

    def create_move(self, move_type):
        pool = Pool()
        Move = pool.get('stock.move')
        moves = super().create_move(move_type)
        for line in self.lines:
            if line.components:
                for component in line.components:
                    move = component.get_move(move_type)
                    if move:
                        moves.append(move)
        Move.save(moves)
        return moves

    @get_shipments_returns('stock.shipment.in')
    def get_shipments(self, name):
        return super().get_shipments(name)

    @get_shipments_returns('stock.shipment.in.return')
    def get_shipment_returns(self, name):
        return super().get_shipment_returns(name)

    @classmethod
    @search_shipments_returns('stock.shipment.in')
    def search_shipments(cls, name, clause):
        return super().search_shipments(name, clause)

    @classmethod
    @search_shipments_returns('stock.shipment.in.return')
    def search_shipment_returns(cls, name, clause):
        return super().search_shipments(name, clause)


class Line(order_line_mixin('purchase'), metaclass=PoolMeta):
    __name__ = 'purchase.line'

    def get_component_order_line(self, component, **values):
        values = values.copy()
        values['purchase'] = self.purchase
        return super().get_component_order_line(component, **values)


class LineComponent(
        order_line_component_mixin('purchase'), ComponentMixin,
        ModelSQL, ModelView):
    "Purchase Line Component"
    __name__ = 'purchase.line.component'

    def get_move(self, move_type):
        from trytond.modules.purchase.exceptions import PartyLocationError
        pool = Pool()
        Move = pool.get('stock.move')
        Date = pool.get('ir.date')

        if (self.quantity >= 0) != (move_type == 'in'):
            return

        quantity = (
            self._get_move_quantity(move_type)
            - self._get_shipped_quantity(move_type))

        quantity = self.unit.round(quantity)
        if quantity <= 0:
            return

        if not self.line.purchase.party.supplier_location:
            raise PartyLocationError(
                gettext('purchase.msg_purchase_supplier_location_required',
                    purchase=self.purchase.rec_name,
                    party=self.purchase.party.rec_name))

        move = Move()
        move.quantity = quantity
        move.uom = self.unit
        move.product = self.product
        move.from_location = self.line.from_location
        move.to_location = self.line.to_location
        move.state = 'draft'
        move.company = self.line.purchase.company
        if move.on_change_with_unit_price_required():
            move.unit_price = round_price(
                self.line.unit_price * self.price_ratio)
            move.currency = self.line.purchase.currency
        if self.moves:
            # backorder can not be planned but shipping date could be used
            # if set in the future
            if (self.line.delivery_date
                    and self.line.delivery_date > Date.today()):
                move.planned_date = self.line.shipping_date
            else:
                move.planned_date = None
        else:
            move.planned_date = self.line.delivery_date
        move.origin = self
        return move

    def _get_move_quantity(self, shipment_type):
        'Return the quantity that should be shipped'
        return abs(self.quantity)


class LineComponentIgnoredMove(ModelSQL):
    'Purchase Line Component - Ignored Move'
    __name__ = 'purchase.line.component-ignored-stock.move'
    component = fields.Many2One(
        'purchase.line.component', "Component",
        ondelete='CASCADE', select=True, required=True)
    move = fields.Many2One(
        'stock.move', "Move", ondelete='RESTRICT', select=True, required=True)


class LineComponentRecreatedMove(ModelSQL):
    'Purchase Line Component - Recreated Move'
    __name__ = 'purchase.line.component-recreated-stock.move'
    component = fields.Many2One(
        'purchase.line.component', "Component",
        ondelete='CASCADE', select=True, required=True)
    move = fields.Many2One(
        'stock.move', "Move", ondelete='RESTRICT', select=True, required=True)


class HandleShipmentException(
        handle_shipment_exception_mixin('purchase'),
        metaclass=PoolMeta):
    __name__ = 'purchase.handle.shipment.exception'


class AmendmentLine(AmendmentLineMixin, metaclass=PoolMeta):
    __name__ = 'purchase.amendment.line'
