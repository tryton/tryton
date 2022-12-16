# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.model import ModelView, Workflow, fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction

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

    carrier = fields.Many2One('carrier', 'Carrier', states={
            'readonly': Eval('state').in_(['done', 'cancelled']),
            },
        depends=['state'])

    cost_used = fields.Function(fields.Numeric(
            "Cost", digits=price_digits,
            states={
                'invisible': Eval('cost_edit', False),
                },
            depends=['cost_edit']),
        'on_change_with_cost_used')
    cost = fields.Numeric(
        "Cost", digits=price_digits,
        states={
            'invisible': ~Eval('cost_edit', False),
            'readonly': Eval('state').in_(['done', 'cancelled']),
            },
        depends=['state'])
    cost_edit = fields.Boolean(
        "Edit Cost",
        states={
            'readonly': Eval('state').in_(['done', 'cancelled']),
            },
        depends=['state'],
        help="Check to edit the cost.")

    def _get_carrier_context(self):
        return {}

    def get_carrier_context(self):
        return self._get_carrier_context()

    @fields.depends('carrier', 'company', methods=['_get_carrier_context'])
    def _compute_costs(self):
        pool = Pool()
        Currency = pool.get('currency.currency')
        costs = {
            'cost': None,
            }
        if self.carrier:
            with Transaction().set_context(self._get_carrier_context()):
                cost, currency_id = self.carrier.get_purchase_price()
            if cost is not None:
                cost = Currency.compute(
                    Currency(currency_id), cost, self.company.currency,
                    round=False)
                costs['cost'] = round_price(cost)
        return costs

    @fields.depends('cost', 'state', 'cost_edit', methods=['_compute_costs'])
    def on_change_with_cost_used(self, name=None):
        cost = self.cost
        if not self.cost_edit and self.state not in {'cancelled', 'done'}:
            cost = self._compute_costs()['cost']
        return cost

    @fields.depends('cost_edit', 'cost_used')
    def on_change_cost_edit(self):
        if self.cost_edit:
            self.cost = self.cost_used

    @property
    def shipment_cost_moves(self):
        raise NotImplementedError

    def _get_shipment_cost(self):
        "Return the cost for the shipment in the company currency"
        return self.cost_used or Decimal(0)

    @classmethod
    def set_shipment_cost(cls, shipments):
        pool = Pool()
        Move = pool.get('stock.move')
        moves = []
        for shipment in shipments:
            cost = shipment._get_shipment_cost()
            if not cost:
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
        for shipment in shipments:
            shipment.cost = shipment.cost_used
        cls.save(shipments)
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
