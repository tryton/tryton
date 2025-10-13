# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from itertools import chain, groupby

from sql import Null
from sql.conditionals import Coalesce
from sql.functions import CharLength

from trytond.i18n import gettext
from trytond.model import (
    Index, ModelSQL, ModelView, Workflow, dualmethod, fields)
from trytond.modules.company.model import employee_field, set_employee
from trytond.modules.product import price_digits, round_price
from trytond.modules.stock.shipment import ShipmentAssignMixin
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, If
from trytond.transaction import Transaction

from .exceptions import CostWarning


class Production(ShipmentAssignMixin, Workflow, ModelSQL, ModelView):
    __name__ = 'production'
    _rec_name = 'number'
    _assign_moves_field = 'inputs'

    number = fields.Char("Number", readonly=True)
    reference = fields.Char(
        "Reference",
        states={
            'readonly': ~Eval('state').in_(['request', 'draft']),
            })
    planned_date = fields.Date('Planned Date',
        states={
            'readonly': Eval('state').in_(['cancelled', 'done']),
            })
    effective_date = fields.Date('Effective Date',
        states={
            'readonly': Eval('state').in_(['cancelled', 'done']),
            })
    planned_start_date = fields.Date('Planned Start Date',
        states={
            'readonly': ~Eval('state').in_(['request', 'draft']),
            'required': Bool(Eval('planned_date')),
            })
    effective_start_date = fields.Date('Effective Start Date',
        states={
            'readonly': Eval('state').in_(['cancelled', 'running', 'done']),
            })
    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': ~Eval('state').in_(['request', 'draft']),
            })
    warehouse = fields.Many2One('stock.location', 'Warehouse', required=True,
        domain=[
            ('type', '=', 'warehouse'),
            ],
        states={
            'readonly': (~Eval('state').in_(['request', 'draft'])
                | Eval('inputs', [-1]) | Eval('outputs', [-1])),
            })
    location = fields.Many2One('stock.location', 'Location', required=True,
        domain=[
            ('type', '=', 'production'),
            ],
        states={
            'readonly': (~Eval('state').in_(['request', 'draft'])
                | Eval('inputs', [-1]) | Eval('outputs', [-1])),
            })
    type = fields.Selection([
            ('assembly', "Assembly"),
            ('disassembly', "Disassembly"),
            ], "Type", required=True,
        states={
            'readonly': ~Eval('state').in_(['request', 'draft']),
            })
    product = fields.Many2One('product.product', 'Product',
        domain=[
            If(Eval('type') == 'assembly',
                ('producible', '=', True),
                ()),
            ],
        states={
            'readonly': ~Eval('state').in_(['request', 'draft']),
            },
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    bom = fields.Many2One('production.bom', 'BOM',
        domain=[
            If(Eval('type') == 'disassembly',
                ('input_products', '=', Eval('product', -1)),
                ('output_products', '=', Eval('product', -1)),
                ),
            ],
        states={
            'readonly': (~Eval('state').in_(['request', 'draft'])
                | ~Eval('warehouse', 0) | ~Eval('location', 0)),
            'invisible': ~Eval('product'),
            })
    uom_category = fields.Function(fields.Many2One(
            'product.uom.category', "UoM Category",
            help="The category of Unit of Measure."),
        'on_change_with_uom_category')
    unit = fields.Many2One(
        'product.uom', "Unit",
        domain=[
            ('category', '=', Eval('uom_category', -1)),
            ],
        states={
            'readonly': ~Eval('state').in_(['request', 'draft']),
            'required': Bool(Eval('bom')),
            'invisible': ~Eval('product'),
            })
    quantity = fields.Float(
        "Quantity", digits='unit',
        states={
            'readonly': ~Eval('state').in_(['request', 'draft']),
            'required': Bool(Eval('bom')),
            'invisible': ~Eval('product'),
            })
    cost = fields.Function(fields.Numeric('Cost', digits=price_digits,
            readonly=True), 'get_cost')
    inputs = fields.One2Many(
        'stock.move', 'production_input', "Input Materials",
        domain=[
            ('shipment', '=', None),
            ('from_location', 'child_of', [Eval('warehouse', -1)], 'parent'),
            ('to_location', '=', Eval('location', -1)),
            ('company', '=', Eval('company', -1)),
            ],
        states={
            'readonly': (~Eval('state').in_(['request', 'draft', 'waiting'])
                | ~Eval('warehouse') | ~Eval('location')),
            })
    outputs = fields.One2Many(
        'stock.move', 'production_output', "Output Materials",
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
            })

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
            ], 'State', readonly=True, sort=False)
    origin = fields.Reference(
        "Origin", selection='get_origin',
        states={
            'readonly': ~Eval('state').in_(['request', 'draft']),
            })

    @classmethod
    def __setup__(cls):
        cls.number.search_unaccented = False
        cls.reference.search_unaccented = False
        super().__setup__()
        t = cls.__table__()
        cls._sql_indexes.update({
                Index(t, (t.reference, Index.Similarity())),
                Index(
                    t,
                    (t.state, Index.Equality(cardinality='low')),
                    where=t.state.in_([
                            'request', 'draft', 'waiting', 'assigned',
                            'running'])),
                })
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
                ('done', 'cancelled'),
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
                'do': {
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

        # Migration from 6.8: rename uom to unit
        if (table_h.column_exist('uom')
                and not table_h.column_exist('unit')):
            table_h.column_rename('uom', 'unit')

        super().__register__(module_name)

    @classmethod
    def order_number(cls, tables):
        table, _ = tables[None]
        return [
            ~((table.state == 'cancelled') & (table.number == Null)),
            CharLength(table.number), table.number]

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

    @classmethod
    def default_type(cls):
        return 'assembly'

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @fields.depends('product', 'bom')
    def compute_lead_time(self, pattern=None):
        pattern = pattern.copy() if pattern is not None else {}
        if self.product and self.product.producible:
            pattern.setdefault('bom', self.bom.id if self.bom else None)
            for line in self.product.production_lead_times:
                if line.match(pattern):
                    return line.lead_time or timedelta()
        return timedelta()

    @fields.depends(
        'planned_date', 'state', 'product', methods=['compute_lead_time'])
    def set_planned_start_date(self):
        if self.state in {'request', 'draft'}:
            if self.planned_date and self.product:
                self.planned_start_date = (
                    self.planned_date - self.compute_lead_time())
            else:
                self.planned_start_date = self.planned_date

    @fields.depends(methods=['set_planned_start_date'])
    def on_change_planned_date(self):
        self.set_planned_start_date()

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

    @fields.depends(
        'company', 'location', methods=['picking_location', 'output_location'])
    def _move(self, type, product, unit, quantity):
        pool = Pool()
        Move = pool.get('stock.move')
        assert type in {'input', 'output'}
        move = Move(**Move.default_get(with_rec_name=False))
        move.product = product
        move.unit = unit
        move.quantity = quantity
        move.company = self.company
        if type == 'input':
            move.from_location = self.picking_location
            move.to_location = self.location
            move.production_input = self
        else:
            move.from_location = self.location
            move.to_location = self.output_location
            move.production_output = self
        move.unit_price_required = move.on_change_with_unit_price_required()
        if move.unit_price_required:
            move.unit_price = Decimal(0)
            if self.company:
                move.currency = self.company.currency
        else:
            move.unit_price = None
            move.currency = None
        return move

    @fields.depends(
        'type', 'bom', 'product', 'unit', 'quantity', 'inputs', 'outputs',
        methods=['_move'])
    def explode_bom(self):
        if not (self.bom and self.product and self.unit):
            return

        factor = self.bom.compute_factor(
            self.product, self.quantity or 0, self.unit,
            type='inputs' if self.type == 'disassembly' else 'outputs')
        inputs = []
        for input_ in self.bom.inputs:
            quantity = input_.compute_quantity(factor)
            for line, quantity in input_.lines_for_quantity(quantity):
                move = self._move(
                    'input', line.product, line.unit, quantity)
                inputs.append(input_.prepare_move(self, move))
        self.inputs = inputs

        outputs = []
        for output in self.bom.outputs:
            quantity = output.compute_quantity(factor)
            for line, quantity in output.lines_for_quantity(quantity):
                move = self._move(
                    'output', line.product, line.unit, quantity)
                outputs.append(output.prepare_move(self, move))
        self.outputs = outputs

    @fields.depends('warehouse')
    def on_change_warehouse(self):
        self.location = None
        if self.warehouse:
            self.location = self.warehouse.production_location

    @fields.depends(
        'product', 'unit', methods=['explode_bom', 'set_planned_start_date'])
    def on_change_product(self):
        if self.product:
            category = self.product.default_uom.category
            if not self.unit or self.unit.category != category:
                self.unit = self.product.default_uom
        else:
            self.bom = None
            self.unit = None
        self.explode_bom()
        self.set_planned_start_date()

    @fields.depends('product')
    def on_change_with_uom_category(self, name=None):
        return self.product.default_uom.category if self.product else None

    @fields.depends(methods=['explode_bom', 'set_planned_start_date'])
    def on_change_bom(self):
        self.explode_bom()
        # Product's production lead time depends on bom
        self.set_planned_start_date()

    @fields.depends(methods=['explode_bom'])
    def on_change_unit(self):
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
            if input_.state == 'cancelled':
                continue
            cost_price = input_.get_cost_price()
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
                    or input_.unit is None
                    or input_.quantity is None
                    or input_.state == 'cancelled'):
                continue
            product = input_.product
            quantity = Uom.compute_qty(
                input_.unit, input_.quantity, product.default_uom)
            cost += Decimal(str(quantity)) * product.cost_price
        return cost

    @dualmethod
    def set_moves(cls, productions):
        pool = Pool()
        Move = pool.get('stock.move')
        to_save = []
        for production in productions:
            dates = production._get_move_planned_date()
            input_date, output_date = dates
            if not production.bom:
                if production.product:
                    move = production._move(
                        'output', production.product, production.unit,
                        production.quantity)
                    move.planned_date = output_date
                    to_save.append(move)
                continue

            factor = production.bom.compute_factor(
                production.product, production.quantity, production.unit)
            for input_ in production.bom.inputs:
                quantity = input_.compute_quantity(factor)
                product = input_.product
                move = production._move(
                    'input', product, input_.unit, quantity)
                move.planned_date = input_date
                to_save.append(input_.prepare_move(production, move))

            for output in production.bom.outputs:
                quantity = output.compute_quantity(factor)
                product = output.product
                move = production._move(
                    'output', product, output.unit, quantity)
                move.planned_date = output_date
                to_save.append(output.prepare_move(production, move))
        Move.save(to_save)

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
                if input_.state == 'cancelled':
                    continue
                cost_price = input_.get_cost_price()
                input_quantities[input_.product] += (
                    Decimal(str(input_.internal_quantity)))
                input_costs[input_.product] += (
                    Decimal(str(input_.internal_quantity)) * cost_price)
            outputs = []
            output_products = set()
            for output in production.outputs:
                if (output.to_location.type == 'lost_found'
                        or output.state == 'cancelled'):
                    continue
                product = output.product
                output_products.add(product)
                if input_quantities.get(output.product):
                    cost_price = (
                        input_costs[product] / input_quantities[product])
                    unit_price = round_price(Uom.compute_price(
                            product.default_uom, cost_price, output.unit))
                    if (output.unit_price != unit_price
                            or output.currency != production.company.currency):
                        output.unit_price = unit_price
                        output.currency = production.company.currency
                        moves.append(output)
                    cost -= min(
                        unit_price * Decimal(str(output.quantity)), cost)
                else:
                    outputs.append(output)
            if not (unique_product := len(output_products) == 1):
                for output in outputs:
                    product = output.product
                    list_price = product.list_price_used
                    if list_price is None:
                        warning_name = Warning.format(
                            'production_missing_list_price', [product])
                        if Warning.check(warning_name):
                            raise CostWarning(warning_name,
                                gettext(
                                    'production.'
                                    'msg_missing_product_list_price',
                                    product=product.rec_name,
                                    production=production.rec_name))
                        continue
                    product_price = (Decimal(str(output.quantity))
                        * Uom.compute_price(
                            product.default_uom, list_price, output.unit))
                    prices[output] = product_price
                    sum_ += product_price

            if not sum_ and (unique_product or production.product):
                prices.clear()
                for output in outputs:
                    if unique_product or output.product == production.product:
                        quantity = Uom.compute_qty(
                            output.unit, output.quantity,
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
                if (output.unit_price != unit_price
                        or output.currency != production.company.currency):
                    output.unit_price = unit_price
                    output.currency = production.company.currency
                    moves.append(output)
        Move.save(moves)

    @classmethod
    def set_number(cls, productions):
        '''
        Fill the number field with the production sequence
        '''
        pool = Pool()
        Config = pool.get('production.configuration')

        config = Config(1)
        for company, c_productions in groupby(
                productions, key=lambda p: p.company):
            c_productions = [p for p in c_productions if not p.number]
            if c_productions:
                sequence = config.get_multivalue(
                    'production_sequence', company=company.id)
                for production, number in zip(
                        c_productions, sequence.get_many(len(c_productions))):
                    production.number = number
        cls.save(productions)

    @classmethod
    def on_modification(cls, mode, productions, field_names=None):
        pool = Pool()
        Move = pool.get('stock.move')
        super().on_modification(mode, productions, field_names=field_names)
        if mode in {'create', 'write'}:
            cls._set_move_planned_date(productions)
        elif mode == 'delete':
            moves = []
            for production in productions:
                moves.extend(production.inputs)
                moves.extend(production.outputs)
            Move.delete(moves)

    @classmethod
    def copy(cls, productions, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('number', None)
        default.setdefault('reference')
        default.setdefault('assigned_by')
        default.setdefault('run_by')
        default.setdefault('done_by')
        default.setdefault('inputs.origin', None)
        default.setdefault('outputs.origin', None)
        return super().copy(productions, default=default)

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
            inputs = [
                m for m in production.inputs
                if m.state not in {'done', 'cancelled'}
                and m.planned_date != input_date]
            if inputs:
                to_write.append(inputs)
                to_write.append({
                        'planned_date': input_date,
                        })
            outputs = [
                m for m in production.outputs
                if m.state not in {'done', 'cancelled'}
                and m.planned_date != output_date]
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
        cls.set_number(productions)
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
        for company, productions in groupby(
                productions, key=lambda p: p.company):
            with Transaction().set_context(company=company.id):
                today = Date.today()
            cls.write([p for p in productions if not p.effective_start_date], {
                    'effective_start_date': today,
                    })

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    @set_employee('done_by')
    def do(cls, productions):
        pool = Pool()
        Move = pool.get('stock.move')
        Date = pool.get('ir.date')
        cls.set_cost(productions)
        Move.do([m for p in productions for m in p.outputs])
        for company, productions in groupby(
                productions, key=lambda p: p.company):
            with Transaction().set_context(company=company.id):
                today = Date.today()
            cls.write([p for p in productions if not p.effective_date], {
                    'effective_date': today,
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
        to_assign = [
            m for p in productions for m in p.assign_moves
            if m.assignation_required]
        if Move.assign_try(to_assign):
            cls.assign(productions)
        else:
            to_assign = []
            for production in productions:
                if any(
                        m.state in {'staging', 'draft'}
                        for m in production.assign_moves
                        if m.assignation_required):
                    continue
                to_assign.append(production)
            if to_assign:
                cls.assign(to_assign)

    @classmethod
    def _get_reschedule_planned_start_dates_domain(cls, date):
        context = Transaction().context
        return [
            ('company', '=', context.get('company')),
            ('state', '=', 'waiting'),
            ('planned_start_date', '<', date),
            ]

    @classmethod
    def _get_reschedule_planned_dates_domain(cls, date):
        context = Transaction().context
        return [
            ('company', '=', context.get('company')),
            ('state', '=', 'running'),
            ('planned_date', '<', date),
            ]

    @classmethod
    def reschedule(cls, date=None):
        pool = Pool()
        Date = pool.get('ir.date')
        if date is None:
            date = Date.today()

        to_reschedule_start_date = cls.search(
            cls._get_reschedule_planned_start_dates_domain(date))
        to_reschedule_planned_date = cls.search(
            cls._get_reschedule_planned_dates_domain(date))

        for production in to_reschedule_start_date:
            production.planned_start_date = date
            production.on_change_planned_start_date()

        for production in to_reschedule_planned_date:
            production.planned_date = date

        cls.save(to_reschedule_start_date + to_reschedule_planned_date)

    @property
    @fields.depends('warehouse')
    def picking_location(self):
        if self.warehouse:
            return (self.warehouse.production_picking_location
                or self.warehouse.storage_location)

    @property
    @fields.depends('warehouse')
    def output_location(self):
        if self.warehouse:
            return (self.warehouse.production_output_location
                or self.warehouse.storage_location)


class Production_Lot(metaclass=PoolMeta):
    __name__ = 'production'

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def do(cls, productions):
        pool = Pool()
        Lot = pool.get('stock.lot')
        Move = pool.get('stock.move')
        lots, moves = [], []
        for production in productions:
            for move in production.outputs:
                if not move.lot and move.product.lot_is_required(
                        move.from_location, move.to_location):
                    move.add_lot()
                    if move.lot:
                        lots.append(move.lot)
                        moves.append(move)
        Lot.save(lots)
        Move.save(moves)
        super().do(productions)
