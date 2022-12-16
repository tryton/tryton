# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model import ModelSQL, ModelView, fields
from trytond.modules.product import round_price
from trytond.pool import Pool, PoolMeta

from .common import (
    AmendmentLineMixin, get_moves, get_shipments_returns,
    handle_shipment_exception_mixin, order_line_component_mixin,
    order_line_mixin, order_mixin, search_moves, search_shipments_returns)
from .product import ComponentMixin


class Sale(order_mixin('sale'), metaclass=PoolMeta):
    __name__ = 'sale.sale'

    def _get_shipment_moves(self, shipment_type):
        moves = super()._get_shipment_moves(shipment_type)
        for line in self.lines:
            if line.components:
                for component in line.components:
                    move = component.get_move(shipment_type)
                    if move:
                        moves[component] = move
        return moves

    @get_shipments_returns('stock.shipment.out')
    def get_shipments(self, name):
        return super().get_shipments(name)

    @get_shipments_returns('stock.shipment.out.return')
    def get_shipment_returns(self, name):
        return super().get_shipment_returns(name)

    @classmethod
    @search_shipments_returns('stock.shipment.out')
    def search_shipments(cls, name, clause):
        return super().search_shipments(name, clause)

    @classmethod
    @search_shipments_returns('stock.shipment.out.return')
    def search_shipment_returns(cls, name, clause):
        return super().search_shipments(name, clause)

    @get_moves
    def get_moves(self, name):
        return super().get_moves(name)

    @classmethod
    @search_moves
    def search_moves(cls, name, clause):
        return super().search_moves(name, clause)


class Line(order_line_mixin('sale'), metaclass=PoolMeta):
    __name__ = 'sale.line'

    def get_component_order_line(self, component, **values):
        values = values.copy()
        values['sale'] = self.sale
        return super().get_component_order_line(component, **values)

    @classmethod
    def get_move_product_types(cls):
        types = super().get_move_product_types()
        types.append('kit')
        return types


class LineComponent(
        order_line_component_mixin('sale'), ComponentMixin,
        ModelSQL, ModelView):
    "Sale Line Component"
    __name__ = 'sale.line.component'

    @property
    def warehouse(self):
        return self.line.warehouse

    def get_move(self, shipment_type):
        from trytond.modules.sale.exceptions import PartyLocationError
        pool = Pool()
        Move = pool.get('stock.move')
        if (shipment_type == 'out') != (self.quantity >= 0):
            return

        quantity = (
            self._get_move_quantity(shipment_type)
            - self._get_shipped_quantity(shipment_type))

        quantity = self.unit.round(quantity)
        if quantity <= 0:
            return

        if not self.line.sale.party.customer_location:
            raise PartyLocationError(
                gettext('sale.msg_sale_customer_location_required',
                    sale=self.sale.rec_name,
                    party=self.sale.party.rec_name))

        move = Move()
        move.quantity = quantity
        move.uom = self.unit
        move.product = self.product
        move.from_location = self.line.from_location
        move.to_location = self.line.to_location
        move.state = 'draft'
        move.company = self.line.sale.company
        if move.on_change_with_unit_price_required():
            move.unit_price = round_price(
                self.line.unit_price * self.price_ratio)
            move.currency = self.line.sale.currency
        move.planned_date = self.line.planned_shipping_date
        move.origin = self
        return move

    def _get_move_quantity(self, shipment_type):
        'Return the quantity that should be shipped'
        pool = Pool()
        Uom = pool.get('product.uom')

        if self.line.sale.shipment_method == 'order':
            return abs(self.quantity)
        elif self.line.sale.shipment_method == 'invoice':
            quantity = 0.0
            for invoice_line in self.line.invoice_lines:
                if (invoice_line.invoice
                        and invoice_line.invoice.state == 'paid'):
                    quantity += Uom.compute_qty(invoice_line.unit,
                        invoice_line.quantity, self.line.unit)
            return self.quantity * quantity / self.line.quantity


class LineComponentIgnoredMove(ModelSQL):
    'Sale Line Component - Ignored Move'
    __name__ = 'sale.line.component-ignored-stock.move'
    component = fields.Many2One(
        'sale.line.component', "Component",
        ondelete='CASCADE', select=True, required=True)
    move = fields.Many2One(
        'stock.move', "Move", ondelete='RESTRICT', select=True, required=True)


class LineComponentRecreatedMove(ModelSQL):
    'Sale Line Component - Recreated Move'
    __name__ = 'sale.line.component-recreated-stock.move'
    component = fields.Many2One(
        'sale.line.component', "Sale Line Component",
        ondelete='CASCADE', select=True, required=True)
    move = fields.Many2One(
        'stock.move', "Move", ondelete='RESTRICT', select=True, required=True)


class HandleShipmentException(
        handle_shipment_exception_mixin('sale'),
        metaclass=PoolMeta):
    __name__ = 'sale.handle.shipment.exception'


class Amendment(metaclass=PoolMeta):
    __name__ = 'sale.amendment'

    @classmethod
    def _stock_moves(cls, line):
        yield from super()._stock_moves(line)
        for component in line.components:
            for move in component.moves:
                if move.state == 'draft':
                    yield move


class AmendmentLine(AmendmentLineMixin, metaclass=PoolMeta):
    __name__ = 'sale.amendment.line'
