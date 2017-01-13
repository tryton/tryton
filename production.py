# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from sql import Null

from trytond.model import ModelView, ModelSQL, Workflow, fields
from trytond.wizard import Wizard, StateTransition, StateView, Button
from trytond.pyson import Eval, Bool, If, Id
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond import backend

from trytond.modules.product import price_digits, TemplateFunction

__all__ = ['Production', 'AssignFailed', 'Assign']

BOM_CHANGES = ['bom', 'product', 'quantity', 'uom', 'warehouse', 'location',
    'company', 'inputs', 'outputs']


class Production(Workflow, ModelSQL, ModelView):
    "Production"
    __name__ = 'production'
    _rec_name = 'number'

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
            'readonly': Eval('state').in_(['cancel', 'done']),
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
            'readonly': Eval('state').in_(['cancel', 'running', 'done']),
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
                | Eval('inputs', True) | Eval('outputs', True)),
            },
        depends=['state'])
    location = fields.Many2One('stock.location', 'Location', required=True,
        domain=[
            ('type', '=', 'production'),
            ],
        states={
            'readonly': (~Eval('state').in_(['request', 'draft'])
                | Eval('inputs', True) | Eval('outputs', True)),
            },
        depends=['state'])
    product = fields.Many2One('product.product', 'Product',
        domain=[
            ('producible', '=', True),
            ],
        states={
            'readonly': ~Eval('state').in_(['request', 'draft']),
            })
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
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
        'on_change_with_unit_digits')
    quantity = fields.Float('Quantity',
        digits=(16, Eval('unit_digits', 2)),
        states={
            'readonly': ~Eval('state').in_(['request', 'draft']),
            'required': Bool(Eval('bom')),
            'invisible': ~Eval('product'),
            },
        depends=['unit_digits'])
    cost = fields.Function(fields.Numeric('Cost', digits=price_digits,
            readonly=True), 'get_cost')
    inputs = fields.One2Many('stock.move', 'production_input', 'Inputs',
        domain=[
            ('shipment', '=', None),
            ('from_location', 'child_of', [Eval('warehouse')], 'parent'),
            ('to_location', '=', Eval('location')),
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
            ('from_location', '=', Eval('location')),
            ('to_location', 'child_of', [Eval('warehouse')], 'parent'),
            ('company', '=', Eval('company', -1)),
            ],
        states={
            'readonly': (Eval('state').in_(['done', 'cancel'])
                | ~Eval('warehouse') | ~Eval('location')),
            },
        depends=['warehouse', 'location', 'company'])
    state = fields.Selection([
            ('request', 'Request'),
            ('draft', 'Draft'),
            ('waiting', 'Waiting'),
            ('assigned', 'Assigned'),
            ('running', 'Running'),
            ('done', 'Done'),
            ('cancel', 'Canceled'),
            ], 'State', readonly=True)

    @classmethod
    def __setup__(cls):
        super(Production, cls).__setup__()
        cls._error_messages.update({
                'uneven_costs': ('The costs of the outputs (%(outputs)s) of '
                    'production "%(production)s" do not match the cost of the '
                    'production (%(costs)s).')
                })
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
                ('request', 'cancel'),
                ('draft', 'cancel'),
                ('waiting', 'cancel'),
                ('assigned', 'cancel'),
                ('cancel', 'draft'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': ~Eval('state').in_(['request', 'draft',
                            'assigned']),
                    },
                'draft': {
                    'invisible': ~Eval('state').in_(['request', 'waiting',
                            'cancel']),
                    'icon': If(Eval('state') == 'cancel',
                        'tryton-clear',
                        If(Eval('state') == 'request',
                            'tryton-go-next',
                            'tryton-go-previous')),
                    },
                'reset_bom': {
                    'invisible': (~Eval('bom')
                        | ~Eval('state').in_(['request', 'draft', 'waiting'])),
                    },
                'wait': {
                    'invisible': ~Eval('state').in_(['draft', 'assigned',
                            'waiting', 'running']),
                    'icon': If(Eval('state').in_(['assigned', 'running']),
                        'tryton-go-previous',
                        If(Eval('state') == 'waiting',
                            'tryton-clear',
                            'tryton-go-next')),
                    },
                'run': {
                    'invisible': Eval('state') != 'assigned',
                    },
                'done': {
                    'invisible': Eval('state') != 'running',
                    },
                'assign_wizard': {
                    'invisible': Eval('state') != 'waiting',
                    },
                'assign_try': {},
                'assign_force': {},
                })

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        table_h = TableHandler(cls, module_name)
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

    @staticmethod
    def default_state():
        return 'draft'

    @classmethod
    def default_warehouse(cls):
        Location = Pool().get('stock.location')
        locations = Location.search(cls.warehouse.domain)
        if len(locations) == 1:
            return locations[0].id

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

    @fields.depends('planned_date', 'product', 'bom')
    def on_change_with_planned_start_date(self, pattern=None):
        if self.planned_date and self.product:
            if pattern is None:
                pattern = {}
            pattern.setdefault('bom', self.bom.id if self.bom else None)
            for line in self.product.lead_times:
                if line.match(pattern):
                    if line.lead_time:
                        return self.planned_date - line.lead_time
                    else:
                        return self.planned_date
        return self.planned_date

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

    def explode_bom(self):
        pool = Pool()
        Uom = pool.get('product.uom')
        Move = pool.get('stock.move')
        if not (self.bom and self.product and self.uom):
            return
        self.cost = Decimal(0)

        if self.warehouse:
            storage_location = self.warehouse.storage_location
        else:
            storage_location = None

        factor = self.bom.compute_factor(self.product, self.quantity or 0,
            self.uom)
        inputs = []
        for input_ in self.bom.inputs:
            quantity = input_.compute_quantity(factor)
            move = self._explode_move_values(storage_location, self.location,
                self.company, input_, quantity)
            if move:
                inputs.append(move)
                quantity = Uom.compute_qty(input_.uom, quantity,
                    input_.product.default_uom, round=False)
                self.cost += (Decimal(str(quantity)) *
                    input_.product.cost_price)
        self.inputs = inputs
        digits = self.__class__.cost.digits
        self.cost = self.cost.quantize(Decimal(str(10 ** -digits[1])))

        digits = Move.unit_price.digits
        digit = Decimal(str(10 ** -digits[1]))
        outputs = []
        for output in self.bom.outputs:
            quantity = output.compute_quantity(factor)
            move = self._explode_move_values(self.location, storage_location,
                self.company, output, quantity)
            if move:
                move.unit_price = Decimal(0)
                if output.product == move.product and quantity:
                    move.unit_price = Decimal(
                        self.cost / Decimal(str(quantity))).quantize(digit)
                outputs.append(move)
        self.outputs = outputs

    @fields.depends('warehouse')
    def on_change_warehouse(self):
        self.location = None
        if self.warehouse:
            self.location = self.warehouse.production_location

    @fields.depends(*BOM_CHANGES)
    def on_change_product(self):
        if self.product:
            category = self.product.default_uom.category
            if not self.uom or self.uom.category != category:
                self.uom = self.product.default_uom
                self.unit_digits = self.product.default_uom.digits
        else:
            self.bom = None
            self.uom = None
            self.unit_digits = 2
        self.explode_bom()

    @fields.depends('product')
    def on_change_with_uom_category(self, name=None):
        if self.product:
            return self.product.default_uom.category.id

    @fields.depends('uom')
    def on_change_with_unit_digits(self, name=None):
        if self.uom:
            return self.uom.digits
        return 2

    @fields.depends(*BOM_CHANGES)
    def on_change_bom(self):
        self.explode_bom()

    @fields.depends(*BOM_CHANGES)
    def on_change_uom(self):
        self.explode_bom()

    @fields.depends(*BOM_CHANGES)
    def on_change_quantity(self):
        self.explode_bom()

    @ModelView.button_change(*BOM_CHANGES)
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

        digits = self.__class__.cost.digits
        return cost.quantize(Decimal(str(10 ** -digits[1])))

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

    def set_moves(self):
        pool = Pool()
        Move = pool.get('stock.move')

        storage_location = self.warehouse.storage_location
        location = self.location
        company = self.company

        if not self.bom:
            if self.product:
                move = self._move(location, storage_location, company,
                    self.product, self.uom, self.quantity)
                if move:
                    move.production_output = self
                    move.unit_price = Decimal(0)
                    move.save()
            self._set_move_planned_date()
            return

        factor = self.bom.compute_factor(self.product, self.quantity, self.uom)
        cost = Decimal(0)
        for input_ in self.bom.inputs:
            quantity = input_.compute_quantity(factor)
            product = input_.product
            move = self._move(storage_location, location, company,
                product, input_.uom, quantity)
            if move:
                move.production_input = self
                move.save()
                cost += (Decimal(str(move.internal_quantity)) *
                    product.cost_price)
        digits = self.__class__.cost.digits
        cost = cost.quantize(Decimal(str(10 ** -digits[1])))

        digits = Move.unit_price.digits
        digit = Decimal(str(10 ** -digits[1]))
        for output in self.bom.outputs:
            quantity = output.compute_quantity(factor)
            product = output.product
            move = self._move(location, storage_location, company,
                product, output.uom, quantity)
            if move:
                move.production_output = self
                if product == self.product:
                    move.unit_price = Decimal(
                        cost / Decimal(str(quantity))).quantize(digit)
                else:
                    move.unit_price = Decimal(0)
                move.save()
        self._set_move_planned_date()

    @classmethod
    def validate(cls, productions):
        super(Production, cls).validate(productions)
        for production in productions:
            production.check_cost()

    def check_cost(self):
        if self.state != 'done':
            return
        cost_price = Decimal(0)
        for output in self.outputs:
            cost_price += (Decimal(str(output.quantity))
                * output.unit_price)
        if not self.company.currency.is_zero(self.cost - cost_price):
            self.raise_user_error('uneven_costs', {
                    'production': self.rec_name,
                    'costs': self.cost,
                    'outputs': cost_price,
                    })

    @classmethod
    def create(cls, vlist):
        Sequence = Pool().get('ir.sequence')
        Config = Pool().get('production.configuration')

        vlist = [x.copy() for x in vlist]
        config = Config(1)
        for values in vlist:
            if values.get('number') is None:
                values['number'] = Sequence.get_id(
                    config.production_sequence.id)
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
        default = default.copy()
        default.setdefault('number', None)
        return super(Production, cls).copy(productions, default=default)

    def _get_move_planned_date(self):
        "Return the planned dates for input and output moves"
        return self.planned_start_date, self.planned_date

    def _set_move_planned_date(self):
        "Set planned date of moves for the shipments"
        pool = Pool()
        Move = pool.get('stock.move')
        dates = self._get_move_planned_date()
        input_date, output_date = dates
        Move.write([m for m in self.inputs
                if m.state not in ('assigned', 'done', 'cancel')], {
                'planned_date': input_date,
                })
        Move.write([m for m in self.outputs
                if m.state not in ('assigned', 'done', 'cancel')], {
                'planned_date': output_date,
                })

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
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
        Move.draft([m for p in productions
                for m in p.inputs + p.outputs])

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
    def assign(cls, productions):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('running')
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
    def done(cls, productions):
        pool = Pool()
        Move = pool.get('stock.move')
        Date = pool.get('ir.date')
        Move.do([m for p in productions for m in p.outputs])
        cls.write([p for p in productions if not p.effective_date], {
                'effective_date': Date.today(),
                })

    @classmethod
    @ModelView.button_action('production.wizard_assign')
    def assign_wizard(self, productions):
        pass

    @classmethod
    @ModelView.button
    def assign_try(cls, productions):
        pool = Pool()
        Move = pool.get('stock.move')
        if Move.assign_try([m for p in productions
                    for m in p.inputs]):
            cls.assign(productions)
            return True
        else:
            return False

    @classmethod
    @ModelView.button
    def assign_force(cls, productions):
        pool = Pool()
        Move = pool.get('stock.move')
        Move.assign([m for p in productions for m in p.inputs])
        cls.assign(productions)


class AssignFailed(ModelView):
    'Assign Production'
    __name__ = 'production.assign.failed'

    moves = fields.Many2Many('stock.move', None, None, 'Moves', readonly=True)

    @staticmethod
    def default_moves():
        pool = Pool()
        Production = pool.get('production')
        production_id = Transaction().context.get('active_id')
        if not production_id:
            return []
        production = Production(production_id)
        return [m.id for m in production.inputs if m.state == 'draft']


class Assign(Wizard):
    'Assign Production'
    __name__ = 'production.assign'

    start = StateTransition()
    failed = StateView('production.assign.failed',
        'production.assign_failed_view_form', [
            Button('Force Assign', 'force', 'tryton-go-next',
                states={
                    'invisible': ~Id('stock',
                        'group_stock_force_assignment').in_(
                        Eval('context', {}).get('groups', [])),
                    }),
            Button('OK', 'end', 'tryton-ok', True),
            ])
    force = StateTransition()

    def transition_start(self):
        pool = Pool()
        Production = pool.get('production')

        if Production.assign_try(
                [Production(Transaction().context['active_id'])]):
            return 'end'
        else:
            return 'failed'

    def transition_force(self):
        pool = Pool()
        Production = pool.get('production')

        Production.assign_force(
            [Production(Transaction().context['active_id'])])
        return 'end'
