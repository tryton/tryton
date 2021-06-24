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


class Line(order_line_mixin('sale'), metaclass=PoolMeta):
    __name__ = 'sale.line'

    def get_component_order_line(self, component, **values):
        values = values.copy()
        values['sale'] = self.sale
        return super().get_component_order_line(component, **values)


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
        Date = pool.get('ir.date')
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
        if self.moves:
            # backorder can not be planned but shipping date could be used
            # if set in the future
            today = Date.today()
            if self.line.shipping_date and self.line.shipping_date > today:
                move.planned_date = self.line.shipping_date
            else:
                move.planned_date = today
        else:
            move.planned_date = self.line.shipping_date
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


class AmendmentLine(AmendmentLineMixin, metaclass=PoolMeta):
    __name__ = 'sale.amendment.line'
