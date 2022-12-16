# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from itertools import chain

from sql import Null
from sql.conditionals import Coalesce

from trytond.i18n import gettext
from trytond.model import ModelView, ModelSQL, Workflow, fields, dualmethod
from trytond.pyson import Eval, Bool, If
from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.company.model import employee_field, set_employee
from trytond.modules.product import price_digits, round_price
from trytond.modules.stock.shipment import ShipmentAssignMixin

from .exceptions import CostWarning


BOM_CHANGES = ['bom', 'product', 'quantity', 'uom', 'warehouse', 'location',
    'company', 'inputs', 'outputs']


class Production(ShipmentAssignMixin, Workflow, ModelSQL, ModelView):
    "Production"
    __name__ = 'production'
    _assign_moves_field = 'inputs'

    number = fields.Char('Number', select=True, readonly=True)
    reference = fields.Char('Reference', select=1,
        states={
            'readonly': ~Eval('state').in_(['request', 'draft']),
            },
        depends=['state'])
    planned_date = fields.Date('Planned Date',
        states={
            'readonly': ~Eval('state').in_(['request', 'draft']),
            },
        depends=['state'])
    effective_date = fields.Date('Effective Date',
        states={
            'readonly': Eval('state').in_(['cancelled', 'done']),
            },
        depends=['state'])
    planned_start_date = fields.Date('Planned Start Date',
        states={
            'readonly': ~Eval('state').in_(['request', 'draft']),
            'required': Bool(Eval('planned_date')),
            },
        depends=['state', 'planned_date'])
    effective_start_date = fields.Date('Effective Start Date',
        states={
            'readonly': Eval('state').in_(['cancelled', 'running', 'done']),
            },
        depends=['state'])
    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': ~Eval('state').in_(['request', 'draft']),
            },
        depends=['state'])
    warehouse = fields.Many2One('stock.location', 'Warehouse', required=True,
        domain=[
            ('type', '=', 'warehouse'),
            ],
        states={
            'readonly': (~Eval('state').in_(['request', 'draft'])
                | Eval('inputs', [-1]) | Eval('outputs', [-1])),
            },
        depends=['state'])
    location = fields.Many2One('stock.location', 'Location', required=True,
        domain=[
            ('type', '=', 'production'),
            ],
        states={
            'readonly': (~Eval('state').in_(['request', 'draft'])
                | Eval('inputs', [-1]) | Eval('outputs', [-1])),
            },
        depends=['state'])
    product = fields.Many2One('product.product', 'Product',
        domain=[
            ('producible', '=', True),
            ],
        states={
            'readonly': ~Eval('state').in_(['request', 'draft']),
            },
        context={
            'company': Eval('company', -1),
            },
        depends=['company'])
    bom = fields.Many2One('production.bom', 'BOM',
        domain=[
            ('output_products', '=', Eval('product', 0)),
            ],
        states={
            'readonly': (~Eval('state').in_(['request', 'draft'])
                | ~Eval('warehouse', 0) | ~Eval('location', 0)),
            'invisible': ~Eval('product'),
            },
        depends=['product'])
    uom_category = fields.Function(fields.Many2One(
            'product.uom.category', 'Uom Category'),
        'on_change_with_uom_category')
    uom = fields.Many2One('product.uom', 'Uom',
        domain=[
            ('category', '=', Eval('uom_category')),
            ],
        states={
            'readonly': ~Eval('state').in_(['request', 'draft']),
            'required': Bool(Eval('bom')),
            'invisible': ~Eval('product'),
            },
        depends=['uom_category'])
    quantity = fields.Float(
        "Quantity", digits='uom',
        states={
            'readonly': ~Eval('state').in_(['request', 'draft']),
            'required': Bool(Eval('bom')),
            'invisible': ~Eval('product'),
            })
    cost = fields.Function(fields.Numeric('Cost', digits=price_digits,
            readonly=True), 'get_cost')
    inputs = fields.One2Many('stock.move', 'production_input', 'Inputs',
        domain=[
            ('shipment', '=', None),
            ('from_location', 'child_of', [Eval('warehouse', -1)], 'parent'),
            ('to_location', '=', Eval('location', -1)),
            ('company', '=', Eval('company', -1)),
            ],
        states={
            'readonly': (~Eval('state').in_(['request', 'draft', 'waiting'])
                | ~Eval('warehouse') | ~Eval('location')),
            },
        depends=['warehouse', 'location', 'company'])
    outputs = fields.One2Many('stock.move', 'production_output', 'Outputs',
        domain=[
            ('shipment', '=', None),
            ('from_location', '=', Eval('location', -1)),
            ['OR',
                ('to_location', 'child_of', [Eval('warehouse', -1)], 'parent'),
                ('to_location.waste_warehouses', '=', Eval('warehouse', -1)),
                ],
            ('company', '=', Eval('company', -1)),
            ],
        states={
            'readonly': (Eval('state').in_(['done', 'cancelled'])
                | ~Eval('warehouse') | ~Eval('location')),
            },
        depends=['warehouse', 'location', 'company'])

    assigned_by = employee_field("Assigned By")
    run_by = employee_field("Run By")
    done_by = employee_field("Done By")
    state = fields.Selection([
            ('request', 'Request'),
            ('draft', 'Draft'),
            ('waiting', 'Waiting'),
            ('assigned', 'Assigned'),
            ('running', 'Running'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled'),
            ], 'State', readonly=True)
    origin = fields.Reference(
        "Origin", selection='get_origin', select=True,
        states={
            'readonly': ~Eval('state').in_(['request', 'draft']),
            },
        depends=['state'])

    @classmethod
    def __setup__(cls):
        super(Production, cls).__setup__()
        cls._order = [
            ('effective_date', 'ASC NULLS LAST'),
            ('id', 'ASC'),
            ]
        cls._transitions |= set((
                ('request', 'draft'),
                ('draft', 'waiting'),
                ('waiting', 'assigned'),
                ('assigned', 'running'),
                ('running', 'done'),
                ('running', 'waiting'),
                ('assigned', 'waiting'),
                ('waiting', 'waiting'),
                ('waiting', 'draft'),
                ('request', 'cancelled'),
                ('draft', 'cancelled'),
                ('waiting', 'cancelled'),
                ('assigned', 'cancelled'),
                ('cancelled', 'draft'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': ~Eval('state').in_(['request', 'draft',
                            'assigned']),
                    'depends': ['state'],
                    },
                'draft': {
                    'invisible': ~Eval('state').in_(['request', 'waiting',
                            'cancelled']),
                    'icon': If(Eval('state') == 'cancelled',
                        'tryton-clear',
                        If(Eval('state') == 'request',
                            'tryton-forward',
                            'tryton-back')),
                    'depends': ['state'],
                    },
                'reset_bom': {
                    'invisible': (~Eval('bom')
                        | ~Eval('state').in_(['request', 'draft', 'waiting'])),
                    'depends': ['state', 'bom'],
                    },
                'wait': {
                    'invisible': ~Eval('state').in_(['draft', 'assigned',
                            'waiting', 'running']),
                    'icon': If(Eval('state').in_(['assigned', 'running']),
                        'tryton-back',
                        If(Eval('state') == 'waiting',
                            'tryton-clear',
                            'tryton-forward')),
                    'depends': ['state'],
                    },
                'run': {
                    'invisible': Eval('state') != 'assigned',
                    'depends': ['state'],
                    },
                'done': {
                    'invisible': Eval('state') != 'running',
                    'depends': ['state'],
                    },
                'assign_wizard': {
                    'invisible': Eval('state') != 'waiting',
                    'depends': ['state'],
                    },
                'assign_try': {},
                'assign_force': {},
                })

    def get_rec_name(self, name):
        items = []
        if self.number:
            items.append(self.number)
        if self.reference:
            items.append('[%s]' % self.reference)
        if not items:
            items.append('(%s)' % self.id)
        return ' '.join(items)

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('number',) + tuple(clause[1:]),
            ('reference',) + tuple(clause[1:]),
            ]

    @classmethod
    def __register__(cls, module_name):
        table_h = cls.__table_handler__(module_name)
        table = cls.__table__()

        # Migration from 3.8: rename code into number
        if table_h.column_exist('code'):
            table_h.column_rename('code', 'number')

        super(Production, cls).__register__(module_name)

        # Migration from 4.0: fill planned_start_date
        cursor = Transaction().connection.cursor()
        cursor.execute(*table.update(
                [table.planned_start_date],
                [table.planned_date],
                where=(table.planned_start_date == Null)
                & (table.planned_date != Null)))

        # Migration from 5.6: rename state cancel to cancelled
        cursor.execute(*table.update(
                [table.state], ['cancelled'],
                where=table.state == 'cancel'))

    @classmethod
    def order_effective_date(cls, tables):
        table, _ = tables[None]
        return [Coalesce(
                table.effective_start_date, table.effective_date,
                table.planned_start_date, table.planned_date)]

    @staticmethod
    def default_state():
        return 'draft'

    @classmethod
    def default_warehouse(cls):
        Location = Pool().get('stock.location')
        return Location.get_default_warehouse()

    @classmethod
    def default_location(cls):
        Location = Pool().get('stock.location')
        warehouse_id = cls.default_warehouse()
        if warehouse_id:
            warehouse = Location(warehouse_id)
            return warehouse.production_location.id

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @fields.depends('product', 'bom')
    def compute_lead_time(self, pattern=None):
        if pattern is None:
            pattern = {}
        if self.product:
            pattern.setdefault('bom', self.bom.id if self.bom else None)
            for line in self.product.lead_times:
                if line.match(pattern):
                    return line.lead_time or timedelta()
        return timedelta()

    @fields.depends('planned_date', methods=['compute_lead_time'])
    def on_change_with_planned_start_date(self, pattern=None):
        if self.planned_date and self.product:
            return self.planned_date - self.compute_lead_time()
        return self.planned_date

    @fields.depends(
        'planned_date', 'planned_start_date', methods=['compute_lead_time'])
    def on_change_planned_start_date(self, pattern=None):
        if self.planned_start_date and self.product:
            planned_date = self.planned_start_date + self.compute_lead_time()
            if (not self.planned_date
                    or self.planned_date < planned_date):
                self.planned_date = planned_date

    @classmethod
    def _get_origin(cls):
        'Return list of Model names for origin Reference'
        return set()

    @classmethod
    def get_origin(cls):
        Model = Pool().get('ir.model')
        get_name = Model.get_name
        models = cls._get_origin()
        return [(None, '')] + [(m, get_name(m)) for m in models]

    def _move(self, from_location, to_location, company, product, uom,
            quantity):
        Move = Pool().get('stock.move')
        move = Move(
            product=product,
            uom=uom,
            quantity=quantity,
            from_location=from_location,
            to_location=to_location,
            company=company,
            currency=company.currency if company else None,
            state='draft',
            )
        return move

    def _explode_move_values(self, from_location, to_location, company,
            bom_io, quantity):
        move = self._move(from_location, to_location, company,
            bom_io.product, bom_io.uom, quantity)
        move.from_location = from_location.id if from_location else None
        move.to_location = to_location.id if to_location else None
        move.unit_price_required = move.on_change_with_unit_price_required()
        return move

    @fields.depends(*BOM_CHANGES)
    def explode_bom(self):
        pool = Pool()
        Uom = pool.get('product.uom')
        if not (self.bom and self.product and self.uom):
            return

        factor = self.bom.compute_factor(self.product, self.quantity or 0,
            self.uom)
        inputs = []
        for input_ in self.bom.inputs:
            quantity = input_.compute_quantity(factor)
            move = self._explode_move_values(
                self.picking_location, self.location, self.company,
                input_, quantity)
            if move:
                inputs.append(move)
                quantity = Uom.compute_qty(input_.uom, quantity,
                    input_.product.default_uom, round=False)
        self.inputs = inputs

        outputs = []
        for output in self.bom.outputs:
            quantity = output.compute_quantity(factor)
            move = self._explode_move_values(
                self.location, self.output_location, self.company, output,
                quantity)
            if move:
                move.unit_price = Decimal(0)
                outputs.append(move)
        self.outputs = outputs

    @fields.depends('warehouse')
    def on_change_warehouse(self):
        self.location = None
        if self.warehouse:
            self.location = self.warehouse.production_location

    @fields.depends('product', 'uom', methods=['explode_bom'])
    def on_change_product(self):
        if self.product:
            category = self.product.default_uom.category
            if not self.uom or self.uom.category != category:
                self.uom = self.product.default_uom
        else:
            self.bom = None
            self.uom = None
        self.explode_bom()

    @fields.depends('product')
    def on_change_with_uom_category(self, name=None):
        if self.product:
            return self.product.default_uom.category.id

    @fields.depends(methods=['explode_bom'])
    def on_change_bom(self):
        self.explode_bom()

    @fields.depends(methods=['explode_bom'])
    def on_change_uom(self):
        self.explode_bom()

    @fields.depends(methods=['explode_bom'])
    def on_change_quantity(self):
        self.explode_bom()

    @ModelView.button_change(methods=['explode_bom'])
    def reset_bom(self):
        self.explode_bom()

    def get_cost(self, name):
        cost = Decimal(0)
        for input_ in self.inputs:
            if input_.cost_price is not None:
                cost_price = input_.cost_price
            else:
                cost_price = input_.product.cost_price
            cost += (Decimal(str(input_.internal_quantity)) * cost_price)
        return round_price(cost)

    @fields.depends('inputs')
    def on_change_with_cost(self):
        Uom = Pool().get('product.uom')

        cost = Decimal(0)
        if not self.inputs:
            return cost

        for input_ in self.inputs:
            if (input_.product is None
                    or input_.uom is None
                    or input_.quantity is None):
                continue
            product = input_.product
            quantity = Uom.compute_qty(input_.uom, input_.quantity,
                product.default_uom)
            cost += Decimal(str(quantity)) * product.cost_price
        return cost

    @dualmethod
    def set_moves(cls, productions):
        pool = Pool()
        Move = pool.get('stock.move')
        to_save = []
        for production in productions:
            location = production.location
            company = production.company

            if not production.bom:
                if production.product:
                    move = production._move(
                        location, production.output_location, company,
                        production.product, production.uom,
                        production.quantity)
                    if move:
                        move.production_output = production
                        move.unit_price = Decimal(0)
                        to_save.append(move)
                continue

            factor = production.bom.compute_factor(
                production.product, production.quantity, production.uom)
            for input_ in production.bom.inputs:
                quantity = input_.compute_quantity(factor)
                product = input_.product
                move = production._move(
                    production.picking_location, location, company, product,
                    input_.uom, quantity)
                if move:
                    move.production_input = production
                    to_save.append(move)

            for output in production.bom.outputs:
                quantity = output.compute_quantity(factor)
                product = output.product
                move = production._move(location, production.output_location,
                    company, product, output.uom, quantity)
                if move:
                    move.production_output = production
                    move.unit_price = Decimal(0)
                    to_save.append(move)
        Move.save(to_save)
        cls._set_move_planned_date(productions)

    @classmethod
    def set_cost_from_moves(cls):
        pool = Pool()
        Move = pool.get('stock.move')
        productions = set()
        moves = Move.search([
                ('production_cost_price_updated', '=', True),
                ('production_input', '!=', None),
                ],
            order=[('effective_date', 'ASC')])
        for move in moves:
            if move.production_input not in productions:
                cls.__queue__.set_cost([move.production_input])
                productions.add(move.production_input)
        Move.write(moves, {'production_cost_price_updated': False})

    @classmethod
    def set_cost(cls, productions):
        pool = Pool()
        Uom = pool.get('product.uom')
        Move = pool.get('stock.move')
        Warning = pool.get('res.user.warning')

        moves = []
        for production in productions:
            sum_ = Decimal(0)
            prices = {}
            cost = production.cost

            input_quantities = defaultdict(Decimal)
            input_costs = defaultdict(Decimal)
            for input_ in production.inputs:
                if input_.cost_price is not None:
                    cost_price = input_.cost_price
                else:
                    cost_price = input_.product.cost_price
                input_quantities[input_.product] += (
                    Decimal(str(input_.internal_quantity)))
                input_costs[input_.product] += (
                    Decimal(str(input_.internal_quantity)) * cost_price)
            outputs = []
            for output in production.outputs:
                if output.to_location.type == 'lost_found':
                    continue
                product = output.product
                if input_quantities.get(output.product):
                    cost_price = (
                        input_costs[product] / input_quantities[product])
                    unit_price = round_price(Uom.compute_price(
                            product.default_uom, cost_price, output.uom))
                    if output.unit_price != unit_price:
                        output.unit_price = unit_price
                        moves.append(output)
                    cost -= min(
                        unit_price * Decimal(str(output.quantity)), cost)
                else:
                    outputs.append(output)

            for output in outputs:
                product = output.product
                list_price = product.list_price_used
                if list_price is None:
                    warning_name = Warning.format(
                        'production_missing_list_price', [product])
                    if Warning.check(warning_name):
                        raise CostWarning(warning_name,
                            gettext(
                                'production.msg_missing_product_list_price',
                                product=product.rec_name,
                                production=production.rec_name))
                    continue
                product_price = (Decimal(str(output.quantity))
                    * Uom.compute_price(
                        product.default_uom, list_price, output.uom))
                prices[output] = product_price
                sum_ += product_price

            if not sum_ and production.product:
                prices.clear()
                for output in outputs:
                    if output.product == production.product:
                        quantity = Uom.compute_qty(
                            output.uom, output.quantity,
                            output.product.default_uom, round=False)
                        quantity = Decimal(str(quantity))
                        prices[output] = quantity
                        sum_ += quantity

            for output in outputs:
                if sum_:
                    ratio = prices.get(output, 0) / sum_
                else:
                    ratio = Decimal(1) / len(outputs)
                if not output.quantity:
                    unit_price = Decimal(0)
                else:
                    quantity = Decimal(str(output.quantity))
                    unit_price = round_price(cost * ratio / quantity)
                if output.unit_price != unit_price:
                    output.unit_price = unit_price
                    moves.append(output)
        Move.save(moves)

    @classmethod
    def create(cls, vlist):
        Config = Pool().get('production.configuration')

        vlist = [x.copy() for x in vlist]
        config = Config(1)
        default_company = cls.default_company()
        for values in vlist:
            if values.get('number') is None:
                values['number'] = config.get_multivalue(
                    'production_sequence',
                    company=values.get('company', default_company)).get()
        productions = super(Production, cls).create(vlist)
        for production in productions:
            production._set_move_planned_date()
        return productions

    @classmethod
    def write(cls, *args):
        super(Production, cls).write(*args)
        for production in sum(args[::2], []):
            production._set_move_planned_date()

    @classmethod
    def copy(cls, productions, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('number', None)
        default.setdefault('assigned_by')
        default.setdefault('run_by')
        default.setdefault('done_by')
        return super(Production, cls).copy(productions, default=default)

    def _get_move_planned_date(self):
        "Return the planned dates for input and output moves"
        return self.planned_start_date, self.planned_date

    @dualmethod
    def _set_move_planned_date(cls, productions):
        "Set planned date of moves for the shipments"
        pool = Pool()
        Move = pool.get('stock.move')
        to_write = []
        for production in productions:
            dates = production._get_move_planned_date()
            input_date, output_date = dates
            inputs = [m for m in production.inputs
                    if m.state not in ('assigned', 'done', 'cancelled')]
            if inputs:
                to_write.append(inputs)
                to_write.append({
                        'planned_date': input_date,
                        })
            outputs = [m for m in production.outputs
                    if m.state not in ('assigned', 'done', 'cancelled')]
            if outputs:
                to_write.append(outputs)
                to_write.append({
                        'planned_date': output_date,
                        })
        if to_write:
            Move.write(*to_write)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, productions):
        pool = Pool()
        Move = pool.get('stock.move')
        Move.cancel([m for p in productions
                for m in p.inputs + p.outputs])

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, productions):
        pool = Pool()
        Move = pool.get('stock.move')

        to_draft, to_delete = [], []
        for production in productions:
            for move in chain(production.inputs, production.outputs):
                if move.state != 'cancelled':
                    to_draft.append(move)
                else:
                    to_delete.append(move)
        Move.draft(to_draft)
        Move.delete(to_delete)

    @classmethod
    @ModelView.button
    @Workflow.transition('waiting')
    def wait(cls, productions):
        pool = Pool()
        Move = pool.get('stock.move')
        Move.draft([m for p in productions
                for m in p.inputs + p.outputs])

    @classmethod
    @Workflow.transition('assigned')
    @set_employee('assigned_by')
    def assign(cls, productions):
        pool = Pool()
        Move = pool.get('stock.move')
        Move.assign([m for p in productions for m in p.assign_moves])

    @classmethod
    @ModelView.button
    @Workflow.transition('running')
    @set_employee('run_by')
    def run(cls, productions):
        pool = Pool()
        Move = pool.get('stock.move')
        Date = pool.get('ir.date')
        Move.do([m for p in productions for m in p.inputs])
        cls.write([p for p in productions if not p.effective_start_date], {
                'effective_start_date': Date.today(),
                })

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    @set_employee('done_by')
    def done(cls, productions):
        pool = Pool()
        Move = pool.get('stock.move')
        Date = pool.get('ir.date')
        cls.set_cost(productions)
        Move.do([m for p in productions for m in p.outputs])
        cls.write([p for p in productions if not p.effective_date], {
                'effective_date': Date.today(),
                })

    @classmethod
    @ModelView.button_action('production.wizard_production_assign')
    def assign_wizard(cls, productions):
        pass

    @dualmethod
    @ModelView.button
    def assign_try(cls, productions):
        pool = Pool()
        Move = pool.get('stock.move')
        if Move.assign_try(
                [m for p in productions for m in p.assign_moves]):
            cls.assign(productions)
            return True
        else:
            return False

    @classmethod
    def _get_reschedule_domain(cls, date):
        context = Transaction().context
        return [
            ('company', '=', context.get('company')),
            ('state', '=', 'waiting'),
            ('planned_start_date', '<', date),
            ]

    @classmethod
    def reschedule(cls, date=None):
        pool = Pool()
        Date = pool.get('ir.date')
        if date is None:
            date = Date.today()
        productions = cls.search(cls._get_reschedule_domain(date))
        for production in productions:
            production.planned_start_date = date
            production.on_change_planned_start_date()
        cls.save(productions)

    @property
    def picking_location(self):
        if self.warehouse:
            return (self.warehouse.production_picking_location
                or self.warehouse.storage_location)

    @property
    def output_location(self):
        if self.warehouse:
            return (self.warehouse.production_output_location
                or self.warehouse.storage_location)
