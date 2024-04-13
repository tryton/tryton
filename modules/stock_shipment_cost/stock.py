# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.model import ModelView, Workflow, fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.product import price_digits, round_price


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    shipment_out_cost_price = fields.Numeric(
        "Shipment Cost Price", digits=price_digits, readonly=True,
        states={
            'invisible': ~Eval('shipment_out_cost_price'),
            },
        )

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._allow_modify_closed_period.add('shipment_out_cost_price')


class ShipmentCostMixin:
    __slots__ = ()

    @property
    def shipment_cost_moves(self):
        raise NotImplementedError

    def _get_shipment_cost(self):
        "Return the cost for the shipment in the company currency"
        return Decimal(0)

    @classmethod
    def set_shipment_cost(cls, shipments):
        pool = Pool()
        Move = pool.get('stock.move')
        moves = []
        for shipment in shipments:
            cost = shipment._get_shipment_cost()
            if cost is None:
                continue

            sum_ = Decimal(0)
            costs = {}
            for move in shipment.shipment_cost_moves:
                move_cost = (
                    move.cost_price * Decimal(str(move.internal_quantity)))
                costs[move] = move_cost
                sum_ += move_cost

            factors = {}
            for move in shipment.shipment_cost_moves:
                if sum_:
                    ratio = costs[move] / sum_
                else:
                    ratio = Decimal(1) / len(shipment.shipment_cost_moves)
                factors[move.id] = ratio
            moves.extend(shipment._allocate_shipment_cost(cost, factors))
        Move.save(moves)

    def _allocate_shipment_cost(self, cost, factors):
        moves = []
        for move in self.shipment_cost_moves:
            ratio = factors[move.id]
            quantity = Decimal(str(move.internal_quantity))
            if quantity and ratio:
                cost_price = round_price(cost * ratio / quantity)
            else:
                cost_price = Decimal(0)
            if move.shipment_out_cost_price != cost_price:
                move.shipment_out_cost_price = cost_price
                moves.append(move)
        return moves

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def done(cls, shipments):
        super().done(shipments)
        cls.set_shipment_cost(shipments)


class ShipmentOut(ShipmentCostMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    @property
    def shipment_cost_moves(self):
        return self.outgoing_moves


class ShipmentOutReturn(ShipmentCostMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.return'

    @property
    def shipment_cost_moves(self):
        return self.incoming_moves
