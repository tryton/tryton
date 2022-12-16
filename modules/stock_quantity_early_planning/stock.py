# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt
from collections import defaultdict
from itertools import groupby

from trytond.model import Model, ModelSQL, ModelView, Workflow, fields
from trytond.modules.company.model import (
    employee_field, reset_employee, set_employee)
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.wizard import Button, StateAction, StateView, Wizard


class QuantityEarlyPlan(Workflow, ModelSQL, ModelView):
    "Stock Quantity Early Plan"
    __name__ = 'stock.quantity.early_plan'

    company = fields.Many2One(
        'company.company', "Company", required=True, select=True)
    origin = fields.Reference(
        "Origin", 'get_origins', required=True,
        domain={
            'stock.move': [
                ('company', '=', Eval('company', -1)),
                ],
            'stock.shipment.out': [
                ('company', '=', Eval('company', -1)),
                ],
            'stock.shipment.in.return': [
                ('company', '=', Eval('company', -1)),
                ],
            'stock.shipment.internal': [
                ('company', '=', Eval('company', -1)),
                ],
            })
    planned_date = fields.Function(
        fields.Date("Planned Date"),
        'on_change_with_planned_date')
    early_quantity = fields.Float(
        "Early Quantity", readonly=True,
        states={
            'invisible': True,
            })
    early_date = fields.Date(
        "Early Date", readonly=True,
        states={
            'invisible': True,
            })
    earlier_date = fields.Function(
        fields.Date("Earlier Date"), 'get_earlier_date')
    earliest_date = fields.Function(
        fields.Date("Earliest Date"), 'get_earliest_date')
    earliest_percentage = fields.Function(
        fields.Float(
            "Earliest Percentage", digits=(1, 4),
            states={
                'invisible': ~Eval('earliest_date'),
                }),
        'get_earliest_percentage')
    warehouse = fields.Function(
        fields.Many2One('stock.location', "Warehouse"),
        'on_change_with_warehouse')
    moves = fields.Function(
        fields.One2Many(
            'stock.quantity.early_plan', None, "Moves",
            states={
                'invisible': ~Eval('moves'),
                }),
        'get_moves')

    processed_by = employee_field("Processed by", states=['processing'])
    closed_by = employee_field("Closed by", states=['closed'])
    ignored_by = employee_field("Ignored by", states=['ignored'])

    state = fields.Selection([
            ('open', "Open"),
            ('processing', "Processing"),
            ('closed', "Closed"),
            ('ignored', "Ignored"),
            ], "State", required=True, readonly=True, select=True, sort=False)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._transitions |= {
            ('open', 'processing'),
            ('open', 'ignored'),
            ('processing', 'closed'),
            ('processing', 'open'),
            ('processing', 'ignored'),
            ('ignored', 'open'),
            }
        cls._buttons.update({
                'open': {
                    'invisible': ~Eval('state').in_(['processing', 'ignored']),
                    'depends': ['state'],
                    },
                'process': {
                    'invisible': Eval('state') != 'open',
                    'depends': ['state'],
                    },
                'close': {
                    'invisible': Eval('state') != 'processing',
                    'depends': ['state'],
                    },
                'ignore': {
                    'invisible': ~Eval('state').in_(['open', 'processing']),
                    'depends': ['state'],
                    },
                })

    @classmethod
    def get_origins(cls):
        pool = Pool()
        Model = pool.get('ir.model')
        get_name = Model.get_name
        models = cls._get_origins()
        return [(m, get_name(m)) for m in models]

    @classmethod
    def _get_origins(cls):
        "Return a list of Model names for origin Reference"
        return [
            'stock.move',
            'stock.shipment.out',
            'stock.shipment.in.return',
            'stock.shipment.internal',
            ]

    @fields.depends('origin')
    def on_change_with_planned_date(self, name=None):
        if isinstance(self.origin, Model) and self.origin.id >= 0:
            return self.origin.planned_date

    def get_earlier_date(self, name):
        return self._get_dates(max)

    def get_earliest_date(self, name):
        return self._get_dates(min)

    @property
    def _allow_partial_moves(self):
        "Allow to early planning without all moves"
        return True

    def _get_dates(self, aggregate):
        pool = Pool()
        Move = pool.get('stock.move')
        if isinstance(self.origin, Move) and self.origin.id >= 0:
            if (aggregate == max
                    and self.early_quantity != self.origin.internal_quantity):
                return self.origin.planned_date
            else:
                return self.early_date
        elif (not self._allow_partial_moves
                and any(not m.early_date for m in self.moves)):
            return self.planned_date
        else:
            return aggregate(
                filter(None, (m._get_dates(aggregate) for m in self.moves)),
                default=self.planned_date)

    @property
    def _early_quantity(self):
        if isinstance(self.origin, Move) and self.origin.id >= 0:
            if self.early_quantity is not None:
                return self.early_quantity
            else:
                return self.origin.internal_quantity

    def get_earliest_percentage(self, name):
        pool = Pool()
        Move = pool.get('stock.move')
        if isinstance(self.origin, Move) and self.origin.id >= 0:
            return round(
                self._early_quantity / self.origin.internal_quantity, 4)
        else:
            date = self._get_dates(min)
            total = sum(m.origin.internal_quantity for m in self.moves)
            quantity = sum(
                m._early_quantity for m in self.moves
                if (m.early_date or m.planned_date or dt.date.max) <= date)
            if total:
                return round(quantity / total, 4)
            else:
                return 1

    @classmethod
    def default_warehouse(cls):
        pool = Pool()
        Location = pool.get('stock.location')
        return Location.get_default_warehouse()

    @fields.depends('origin')
    def on_change_with_warehouse(self, name=None):
        pool = Pool()
        Move = pool.get('stock.move')
        if isinstance(self.origin, Move) and self.origin.id >= 0:
            warehouse = self.origin.from_location.warehouse
            if warehouse:
                return warehouse.id
        elif (isinstance(self.origin, Model) and self.origin.id >= 0
                and getattr(self.origin, 'warehouse', None)):
            return self.origin.warehouse.id

    def get_moves(self, name):
        pool = Pool()
        ShipmentOut = pool.get('stock.shipment.out')
        ShipmentInReturn = pool.get('stock.shipment.in.return')
        ShipmentInternal = pool.get('stock.shipment.internal')
        moves = []
        if isinstance(self.origin, (
                    ShipmentOut, ShipmentInReturn, ShipmentInternal)):
            for move in self.origin.moves:
                moves.extend([p.id for p in move.quantity_early_plans])
        return moves

    @classmethod
    def default_state(cls):
        return 'open'

    def get_rec_name(self, name):
        return (self.origin.rec_name if isinstance(self.origin, Model)
            else '(%s)' % self.id)

    @classmethod
    @ModelView.button
    @Workflow.transition('open')
    @reset_employee('processed_by', 'ignored_by')
    def open(cls, plans):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('processing')
    @set_employee('processed_by')
    def process(cls, plans):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('closed')
    @set_employee('closed_by')
    def close(cls, plans):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('ignored')
    @set_employee('ignored_by')
    def ignore(cls, plans):
        pass

    @classmethod
    def generate_plans(cls, warehouses=None, company=None):
        """
        For each outgoing move it creates an early plan and a plan for its
        shipment.

        If warehouses is specified it searches only for moves from them.
        """
        pool = Pool()
        Date = pool.get('ir.date')
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')
        User = pool.get('res.user')

        if warehouses is None:
            warehouses = Location.search([
                    ('type', '=', 'warehouse'),
                    ])
        if company is None:
            company = User(Transaction().user).company

        with Transaction().set_context(company=company.id):
            today = Date.today()

        # Do not keep former plan as the may no more be valid
        opens = cls.search([
                ('company', '=', company.id),
                ('state', '=', 'open'),
                ])
        opens = [
            p for p in opens if p.warehouse in warehouses or not p.warehouse]
        cls.delete(opens)

        plans = {}
        for plan in cls.search([
                    ('company', '=', company.id),
                    ('state', 'in', ['processing', 'ignored']),
                    ]):
            if plan.warehouse not in warehouses:
                continue
            plans[plan.origin] = plan

        for warehouse in warehouses:
            moves = Move.search([
                    ('company', '=', company.id),
                    ('from_location', 'child_of', [warehouse.id], 'parent'),
                    ('to_location', 'not child_of', [warehouse.id], 'parent'),
                    ('planned_date', '>', today),
                    ('state', '=', 'draft'),
                    ],
                order=[('product.id', 'ASC'), ('planned_date', 'ASC')])

            for product, moves in groupby(moves, lambda m: m.product):
                for move in moves:
                    earlier_date, quantity = cls._get_earlier_date(
                        move, warehouse)
                    plan = cls._add(move, plans)
                    if earlier_date < move.planned_date:
                        plan.early_date = earlier_date
                    else:
                        plan.early_date = None
                    plan.early_quantity = quantity

                    for parent in cls._parents(move):
                        cls._add(parent, plans)
        cls.save(plans.values())

        to_delete = []
        for plan in cls.browse(plans.values()):
            if (plan.state == 'open'
                    and not isinstance(plan.origin, Move)
                    and plan.earliest_date == plan.planned_date):
                to_delete.append(plan)
        cls.delete(to_delete)

        # Update early date based on internal incoming requests
        for warehouse in warehouses:
            product_plans = cls.search([
                    ('company', '=', company.id),
                    ('state', '=', 'open'),
                    ('origin', 'like', 'stock.move,%'),
                    ],
                order=[('early_date', 'ASC NULLS LAST')])

            in_plans = cls.search([
                    ('company', '=', company.id),
                    ('state', 'in', ['open', 'processing']),
                    cls._incoming_domain(),
                    ])
            product2in = defaultdict(lambda: defaultdict(list))
            for plan in in_plans:
                products = defaultdict(int)
                for product, quantity in plan._incoming_quantities(warehouse):
                    products[product] += quantity
                for product, quantity in products.items():
                    product2in[product][plan.planned_date].append(
                        (quantity, plan))

            to_save = []
            products = set()
            for product_plan in product_plans:
                if product_plan.warehouse != warehouse:
                    continue
                product = product_plan.origin.product
                quantity = product_plan.origin.internal_quantity
                plans = product2in[product][product_plan.early_date]
                plans = cls._pick_incoming(quantity, plans)
                if plans:
                    incoming_products = {p
                        for pl in plans
                        for p, q in pl._incoming_quantities(warehouse)}
                    if incoming_products & products:
                        cls.save(to_save)
                        del to_save[:]
                        products.clear()

                    earlier_date = max(p.earlier_date for p in plans)

                    if (not product_plan.early_date
                            or product_plan.early_date > earlier_date):
                        product_plan.early_date = earlier_date
                        to_save.append(product_plan)
                        products.add(product)
            cls.save(to_save)

    @classmethod
    def _get_earlier_date(cls, move, warehouse):
        pool = Pool()
        Date = pool.get('ir.date')
        ProductQuantitiesByWarehouse = pool.get(
            'stock.product_quantities_warehouse')
        product = move.product
        with Transaction().set_context(company=move.company.id):
            today = Date.today()

        quantity = move.internal_quantity
        if product.consumable:
            return today, quantity

        with Transaction().set_context(
                product=product.id,
                warehouse=warehouse.id,
                stock_skip_warehouse=False,
                ):
            product_quantities = (
                ProductQuantitiesByWarehouse.search([
                        ('date', '>=', today),
                        ('date', '<=', move.planned_date),
                        ],
                    order=[('date', 'DESC')]))
            future_product_quantities = (
                ProductQuantitiesByWarehouse.search([
                        ('date', '>=', move.planned_date),
                        ]))
            min_future_product_quantity = min(
                p.quantity for p in future_product_quantities)
        earlier_date = move.planned_date
        if product_quantities and product_quantities[0].quantity >= 0:
            assert product_quantities[0].date == move.planned_date
            if product_quantities[0].quantity > -quantity:
                # The new date must left the same available
                # quantity for other moves at the current date
                min_quantity = (
                    product_quantities[0].quantity
                    + move.internal_quantity)
                quantity = min(min_quantity, move.internal_quantity)
                if min_future_product_quantity > 0:
                    # The remaining quantities can be used
                    min_quantity -= min_future_product_quantity
                if quantity >= 0:
                    for product_quantity in product_quantities[1:]:
                        if product_quantity.quantity < min_quantity:
                            if earlier_date == move.planned_date:
                                # Not found earlier date,
                                # try with the first smaller quantity
                                quantity = min(
                                    quantity, product_quantity.quantity)
                                min_quantity = min(
                                    product_quantity.quantity,
                                    move.internal_quantity)
                            else:
                                break
                        earlier_date = product_quantity.date
        return earlier_date, quantity

    @classmethod
    def _add(cls, origin, plans):
        if origin in plans:
            plan = plans[origin]
        else:
            plan = plans[origin] = cls(
                company=origin.company,
                origin=origin)
        return plan

    @classmethod
    def _parents(cls, move):
        if move.shipment:
            yield move.shipment

    @classmethod
    def _incoming_domain(cls):
        return ['OR',
            ('origin.state', '=', 'request', 'stock.shipment.internal'),
            ]

    def _incoming_quantities(self, warehouse):
        pool = Pool()
        ShipmentInternal = pool.get('stock.shipment.internal')
        if isinstance(self.origin, ShipmentInternal):
            shipment = self.origin
            if (shipment.to_location.warehouse == warehouse
                    or shipment.from_location.warehouse != warehouse):
                for move in shipment.outgoing_moves:
                    yield move.product, move.internal_quantity

    @classmethod
    def _pick_incoming(cls, quantity, plans):
        plans = [p for q, p in plans if q >= quantity]
        plans.sort(key=lambda p: p.earlier_date)
        return plans


class QuantityEarlyPlanProduction(metaclass=PoolMeta):
    __name__ = 'stock.quantity.early_plan'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.origin.domain['production'] = [
            ('company', '=', Eval('company', -1)),
            ]

    @classmethod
    def _get_origins(cls):
        return super()._get_origins() + ['production']

    @property
    def _allow_partial_moves(self):
        pool = Pool()
        Production = pool.get('production')
        allow = super()._allow_partial_moves
        if (isinstance(self.origin, Production)
                and any(not m.early_date for m in self.moves)):
            allow = False
        return allow

    def get_moves(self, name):
        pool = Pool()
        Production = pool.get('production')
        moves = super().get_moves(name)
        if isinstance(self.origin, Production):
            for move in self.origin.inputs + self.origin.outputs:
                moves.extend([p.id for p in move.quantity_early_plans])
        return moves

    @classmethod
    def _parents(cls, move):
        yield from super()._parents(move)
        if move.production_input:
            yield move.production_input
        if move.production_output:
            yield move.production_output

    @classmethod
    def _incoming_domain(cls):
        return super()._incoming_domain() + [
            ('origin.state', '=', 'request', 'production'),
            ]

    def _incoming_quantities(self, warehouse):
        pool = Pool()
        Production = pool.get('production')
        yield from super()._incoming_quantities(warehouse)
        if isinstance(self.origin, Production):
            production = self.origin
            if production.warehouse == warehouse:
                for output in production.outputs:
                    yield output.product, output.internal_quantity


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    quantity_early_plans = fields.One2Many(
        'stock.quantity.early_plan', 'origin',
        "Quantity Early Plans", readonly=True,
        order=[('early_date', 'ASC NULLS LAST')])


class QuantityEarlyPlanGenerate(Wizard):
    "Stock Quantity Early Plan Generate"
    __name__ = 'stock.quantity.early_plan.generate'
    start = StateView(
        'stock.quantity.early_plan.generate.start',
        'stock_quantity_early_planning'
        '.quantity_early_plan_generate_start_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Generate", 'generate', 'tryton-ok', default=True),
            ])
    generate = StateAction(
        'stock_quantity_early_planning.act_quantity_early_plan_form')

    def transition_generate(self):
        pool = Pool()
        QuantityEarlyPlan = pool.get('stock.quantity.early_plan')
        QuantityEarlyPlan.generate_plans(
            warehouses=self.start.warehouses or None)
        return 'end'


class QuantityEarlyPlanGenerateStart(ModelView):
    "Stock Quantity Early Plan Generate"
    __name__ = 'stock.quantity.early_plan.generate.start'
    warehouses = fields.Many2Many(
        'stock.location', None, None, "Warehouses",
        domain=[
            ('type', '=', 'warehouse'),
            ],
        help="If empty all warehouses are used.")

    @classmethod
    def default_warehouses(cls):
        pool = Pool()
        Location = pool.get('stock.location')
        warehouse = Location.get_default_warehouse()
        if warehouse:
            return [warehouse]
