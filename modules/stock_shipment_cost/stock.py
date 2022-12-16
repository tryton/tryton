# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from sql import Null

from trytond.model import ModelView, Workflow, fields
from trytond.modules.product import price_digits, round_price
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction


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
            'readonly': Eval('shipment_cost_readonly', True),
            })

    cost_currency_used = fields.Function(fields.Many2One(
            'currency.currency', "Cost Currency",
            states={
                'readonly': (
                    Eval('shipment_cost_readonly', True)
                    | ~Eval('cost_edit', False)),
                }),
        'on_change_with_cost_currency_used', setter='set_cost')
    cost_currency = fields.Many2One(
        'currency.currency', "Cost Currency",
        states={
            'required': Bool(Eval('cost')),
            'readonly': Eval('shipment_cost_readonly', True),
            })

    cost_used = fields.Function(fields.Numeric(
            "Cost", digits=price_digits,
            states={
                'readonly': (
                    Eval('shipment_cost_readonly', True)
                    | ~Eval('cost_edit', False)),
                }),
        'on_change_with_cost_used', setter='set_cost')
    cost = fields.Numeric("Cost", digits=price_digits, readonly=True)
    cost_edit = fields.Boolean(
        "Edit Cost",
        states={
            'readonly': Eval('shipment_cost_readonly', True),
            'invisible': Eval('shipment_cost_readonly', True),
            },
        help="Check to edit the cost.")

    shipment_cost_readonly = fields.Function(
        fields.Boolean("Shipment Cost Read Only"),
        'on_change_with_shipment_cost_readonly')

    def _get_carrier_context(self):
        return {}

    def get_carrier_context(self):
        return self._get_carrier_context()

    @fields.depends('carrier', 'company', methods=['_get_carrier_context'])
    def _compute_costs(self):
        costs = {
            'cost': None,
            'cost_currency': None,
            }
        if self.carrier:
            with Transaction().set_context(self._get_carrier_context()):
                cost, currency_id = self.carrier.get_purchase_price()
            if cost is not None:
                costs['cost'] = round_price(cost)
                costs['cost_currency'] = currency_id
        return costs

    @fields.depends(
        'cost_currency', 'cost_edit',
        methods=['_compute_costs', 'on_change_with_shipment_cost_readonly'])
    def on_change_with_cost_currency_used(self, name=None):
        readonly = self.on_change_with_shipment_cost_readonly()
        if not self.cost_edit and not readonly:
            return self._compute_costs()['cost_currency']
        elif self.cost_currency:
            return self.cost_currency.id

    @fields.depends(
        'cost', 'cost_edit',
        methods=['_compute_costs', 'on_change_with_shipment_cost_readonly'])
    def on_change_with_cost_used(self, name=None):
        cost = self.cost
        readonly = self.on_change_with_shipment_cost_readonly()
        if not self.cost_edit and not readonly:
            cost = self._compute_costs()['cost']
        return cost

    @classmethod
    def set_cost(cls, lines, name, value):
        if name.endswith('_used'):
            name = name[:-len('_used')]
        cls.write([l for l in lines if l.cost_edit], {
                name: value,
                })

    def on_change_with_shipment_cost_readonly(self, name=None):
        raise NotImplementedError

    @classmethod
    def index_set_field(cls, name):
        index = super().index_set_field(name)
        if name == 'cost_used':
            index = cls.index_set_field('cost_currency_used') + 1
        return index

    @property
    def shipment_cost_moves(self):
        raise NotImplementedError

    def _get_shipment_cost(self):
        "Return the cost for the shipment in the company currency"
        pool = Pool()
        Currency = pool.get('currency.currency')
        if self.cost_used:
            return Currency.compute(
                self.cost_currency_used, self.cost_used,
                self.company.currency, round=False)
        else:
            return Decimal(0)


class ShipmentOutCostMixin(ShipmentCostMixin):

    @classmethod
    def __register__(cls, module):
        pool = Pool()
        Company = pool.get('company.company')
        table = cls.__table__()
        table_h = cls.__table_handler__(module)
        company = Company.__table__()
        cursor = Transaction().connection.cursor()

        cost_currency_exists = table_h.column_exist('cost_currency')

        super().__register__(module)

        # Migration from 6.4: fill cost_currency
        if not cost_currency_exists:
            cursor.execute(*table.update(
                    columns=[table.cost_currency],
                    values=[company.select(
                            company.currency,
                            where=company.id == table.company)],
                    where=table.cost != Null))

    @fields.depends('state')
    def on_change_with_shipment_cost_readonly(self, name=None):
        return self.state in {'done', 'cancelled'}

    @classmethod
    def set_shipment_cost(cls, shipments):
        pool = Pool()
        Move = pool.get('stock.move')
        moves = []
        for shipment in shipments:
            cost = shipment._get_shipment_cost()
            if not cost:
                continue
            factors = getattr(shipment,
                '_get_allocation_shipment_cost_factors_by_%s' %
                shipment.allocation_shipment_cost_method)()
            moves.extend(shipment._allocate_shipment_cost(cost, factors))
        Move.save(moves)

    @property
    def allocation_shipment_cost_method(self):
        if self.carrier:
            return self.carrier.shipment_cost_allocation_method
        return 'cost'

    def _get_allocation_shipment_cost_factors_by_cost(self):
        sum_ = Decimal(0)
        costs = {}
        for move in self.shipment_cost_moves:
            move_cost = (
                move.cost_price * Decimal(str(move.internal_quantity)))
            costs[move] = move_cost
            sum_ += move_cost

        factors = {}
        for move in self.shipment_cost_moves:
            if sum_:
                ratio = costs[move] / sum_
            else:
                ratio = Decimal(1) / len(self.shipment_cost_moves)
            factors[move.id] = ratio
        return factors

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
            shipment.cost_currency = shipment.cost_currency_used
        cls.save(shipments)
        super().done(shipments)
        cls.set_shipment_cost(shipments)


class ShipmentOut(ShipmentOutCostMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    @property
    def shipment_cost_moves(self):
        return self.outgoing_moves


class ShipmentOutReturn(ShipmentOutCostMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.return'

    @property
    def shipment_cost_moves(self):
        return self.incoming_moves
