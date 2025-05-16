# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from decimal import Decimal

from trytond.i18n import gettext
from trytond.model import ModelSQL, ModelView, fields
from trytond.modules.product import round_price
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

from .common import (
    AmendmentLineMixin, get_moves, get_shipments_returns,
    handle_shipment_exception_mixin, order_line_component_mixin,
    order_line_mixin, order_mixin, search_moves, search_shipments_returns)
from .product import ComponentMixin


class Purchase(order_mixin('purchase'), metaclass=PoolMeta):
    __name__ = 'purchase.purchase'

    def create_move(self, move_type):
        moves = super().create_move(move_type)
        for line in self.lines:
            if line.components:
                for component in line.components:
                    move = component.get_move(move_type)
                    if move:
                        moves.append(move)
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
        return super().search_shipment_returns(name, clause)

    @get_moves
    def get_moves(self, name):
        return super().get_moves(name)

    @classmethod
    @search_moves
    def search_moves(cls, name, clause):
        return super().search_moves(name, clause)


class Line(order_line_mixin('purchase'), metaclass=PoolMeta):
    __name__ = 'purchase.line'

    def get_component_order_line(self, component, **values):
        values = values.copy()
        values['purchase'] = self.purchase
        line = super().get_component_order_line(component, **values)
        if line.unit_price is None:
            line.unit_price = round_price(Decimal(0))
        return line

    @classmethod
    def movable_types(cls):
        return super().movable_types() + ['kit']


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

        with Transaction().set_context(company=self.line.purchase.company.id):
            today = Date.today()

        move = Move()
        move.quantity = quantity
        move.unit = self.unit
        move.product = self.product
        move.from_location = self.line.from_location
        move.to_location = self.line.to_location
        move.state = 'draft'
        move.company = self.line.purchase.company
        if move.on_change_with_unit_price_required():
            move.unit_price = round_price(
                self.line.unit_price * self.price_ratio)
            move.currency = self.line.purchase.currency
        else:
            move.unit_price = None
            move.currency = None
        move.planned_date = self.line.planned_delivery_date
        if move.planned_date and move.planned_date < today:
            move.planned_date = None
        move.origin = self
        move.origin_planned_date = move.planned_date
        return move

    def _get_move_quantity(self, shipment_type):
        'Return the quantity that should be shipped'
        return abs(self.quantity)

    def check_move_quantity(self):
        from trytond.modules.purchase.exceptions import PurchaseMoveQuantity
        pool = Pool()
        Lang = pool.get('ir.lang')
        Warning = pool.get('res.user.warning')
        lang = Lang.get()
        move_type = 'in' if self.quantity >= 0 else 'return'
        quantity = (
            self._get_move_quantity(move_type)
            - self._get_shipped_quantity(move_type))
        if quantity < 0:
            warning_name = Warning.format(
                'check_move_quantity', [self])
            if Warning.check(warning_name):
                raise PurchaseMoveQuantity(warning_name, gettext(
                        'purchase.msg_purchase_line_move_quantity',
                        line=self.rec_name,
                        extra=lang.format_number_symbol(
                            -quantity, self.unit),
                        quantity=lang.format_number_symbol(
                            self.quantity, self.unit)))


class LineComponentIgnoredMove(ModelSQL):
    'Purchase Line Component - Ignored Move'
    __name__ = 'purchase.line.component-ignored-stock.move'
    component = fields.Many2One(
        'purchase.line.component', "Component",
        ondelete='CASCADE', required=True)
    move = fields.Many2One(
        'stock.move', "Move", ondelete='RESTRICT', required=True)


class LineComponentRecreatedMove(ModelSQL):
    'Purchase Line Component - Recreated Move'
    __name__ = 'purchase.line.component-recreated-stock.move'
    component = fields.Many2One(
        'purchase.line.component', "Component",
        ondelete='CASCADE', required=True)
    move = fields.Many2One(
        'stock.move', "Move", ondelete='RESTRICT', required=True)


class HandleShipmentException(
        handle_shipment_exception_mixin('purchase'),
        metaclass=PoolMeta):
    __name__ = 'purchase.handle.shipment.exception'


class Amendment(metaclass=PoolMeta):
    __name__ = 'purchase.amendment'

    @classmethod
    def _stock_moves(cls, line):
        yield from super()._stock_moves(line)
        for component in line.components:
            for move in component.moves:
                if move.state == 'draft':
                    yield move


class AmendmentLine(AmendmentLineMixin, metaclass=PoolMeta):
    __name__ = 'purchase.amendment.line'
