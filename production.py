#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.model import ModelView, ModelSQL, Workflow, fields
from trytond.wizard import Wizard, StateTransition, StateView, Button
from trytond.pyson import Eval, Bool, If, Id
from trytond.pool import Pool
from trytond.transaction import Transaction

__all__ = ['Production', 'AssignFailed', 'Assign']

BOM_CHANGES = ['bom', 'product', 'quantity', 'uom', 'warehouse', 'location',
    'company', 'inputs', 'outputs']


class Production(Workflow, ModelSQL, ModelView):
    "Production"
    __name__ = 'production'
    _rec_name = 'code'

    code = fields.Char('Code', select=True, readonly=True)
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
    effective_date = fields.Date('Effective Date', readonly=True)
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
        on_change=['warehouse'],
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
            ('type', '!=', 'service'),
            ],
        states={
            'readonly': ~Eval('state').in_(['request', 'draft']),
            },
        on_change=BOM_CHANGES)
    bom = fields.Many2One('production.bom', 'BOM',
        domain=[
            ('output_products', '=', Eval('product', 0)),
            ],
        states={
            'readonly': ~Eval('state').in_(['request', 'draft']),
            'invisible': ~Eval('product'),
            },
        on_change=BOM_CHANGES,
        depends=['product'])
    uom_category = fields.Function(fields.Many2One(
            'product.uom.category', 'Uom Category',
            on_change_with=['product']), 'on_change_with_uom_category')
    uom = fields.Many2One('product.uom', 'Uom',
        domain=[
            ('category', '=', Eval('uom_category')),
            ],
        states={
            'readonly': ~Eval('state').in_(['request', 'draft']),
            'required': Bool(Eval('bom')),
            'invisible': ~Eval('product'),
            },
        on_change=BOM_CHANGES,
        depends=['uom_category'])
    unit_digits = fields.Function(fields.Integer('Unit Digits',
            on_change_with=['uom']), 'on_change_with_unit_digits')
    quantity = fields.Float('Quantity',
        digits=(16, Eval('unit_digits', 2)),
        states={
            'readonly': ~Eval('state').in_(['request', 'draft']),
            'required': Bool(Eval('bom')),
            'invisible': ~Eval('product'),
            },
        on_change=BOM_CHANGES,
        depends=['unit_digits'])
    cost = fields.Function(fields.Numeric('Cost', digits=(16, 4),
            readonly=True, on_change_with=['inputs']), 'get_cost')
    inputs = fields.One2Many('stock.move', 'production_input', 'Inputs',
        domain=[
            ('from_location', 'child_of', [Eval('warehouse')], 'parent'),
            ('to_location', '=', Eval('location')),
            ],
        states={
            'readonly': (~Eval('state').in_(['request', 'draft', 'waiting'])
                | ~Eval('location')),
            },
        depends=['warehouse', 'location'])
    outputs = fields.One2Many('stock.move', 'production_output', 'Outputs',
        domain=[
            ('from_location', '=', Eval('location')),
            ('to_location', 'child_of', [Eval('warehouse')], 'parent'),
            ],
        states={
            'readonly': (Eval('state').in_(['done', 'cancel'])
                | ~Eval('location')),
            },
        depends=['warehouse', 'location'])
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
                'missing_cost': ('Production "%s" misses costs on '
                    'some of its outputs.'),
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
                    'readonly': ~Eval('groups', []).contains(
                        Id('stock', 'group_stock')),
                    },
                'assign_try': {},
                'assign_force': {},
                })

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
        pool = Pool()
        Move = pool.get('stock.move')

        move = self._move(from_location, to_location, company,
            bom_io.product, bom_io.uom, quantity)
        move.from_location = from_location.id if from_location else None
        move.to_location = to_location.id if to_location else None
        move.unit_price_required = move.on_change_with_unit_price_required()
        values = {}
        for field_name, field in Move._fields.iteritems():
            try:
                value = getattr(move, field_name)
            except AttributeError:
                continue
            if value and field._type in ('many2one', 'one2one'):
                values[field_name] = value.id
                values[field_name + '.rec_name'] = value.rec_name
            else:
                values[field_name] = value
        return values

    def explode_bom(self):
        pool = Pool()
        Uom = pool.get('product.uom')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        if not (self.bom and self.product and self.uom):
            return {}
        inputs = {
            'remove': [r.id for r in self.inputs or []],
            'add': [],
            }
        outputs = {
            'remove': [r.id for r in self.outputs or []],
            'add': [],
            }
        changes = {
            'inputs': inputs,
            'outputs': outputs,
            'cost': Decimal(0),
            }

        if self.warehouse:
            storage_location = self.warehouse.storage_location
        else:
            storage_location = None

        factor = self.bom.compute_factor(self.product, self.quantity or 0,
            self.uom)
        for input_ in self.bom.inputs:
            quantity = input_.compute_quantity(factor)
            values = self._explode_move_values(storage_location, self.location,
                self.company, input_, quantity)
            if values:
                inputs['add'].append(values)
                quantity = Uom.compute_qty(input_.uom, quantity,
                    input_.product.default_uom)
                changes['cost'] += (Decimal(str(quantity)) *
                    input_.product.cost_price)

        if hasattr(Product, 'cost_price'):
            digits = Product.cost_price.digits
        else:
            digits = Template.cost_price.digits
        for output in self.bom.outputs:
            quantity = output.compute_quantity(factor)
            values = self._explode_move_values(self.location, storage_location,
                self.company, output, quantity)
            if values:
                values['unit_price'] = Decimal(0)
                if output.product.id == values.get('product') and quantity:
                    values['unit_price'] = Decimal(
                        changes['cost'] / Decimal(str(quantity))
                        ).quantize(Decimal(str(10 ** -digits[1])))
                outputs['add'].append(values)
        return changes

    def on_change_warehouse(self):
        changes = {
            'location': None,
            }
        if self.warehouse:
            changes['location'] = self.warehouse.production_location.id
        return changes

    def on_change_product(self):
        result = {}
        if self.product:
            uoms = self.product.default_uom.category.uoms
            if (not self.uom or self.uom not in uoms):
                result['uom'] = self.product.default_uom.id
                result['uom.rec_name'] = self.product.default_uom.rec_name
                result['unit_digits'] = self.product.default_uom.digits
        else:
            result['bom'] = None
            result['uom'] = None
            result['uom.rec_name'] = ''
            result['unit_digits'] = 2

        if 'uom' in result:
            self.uom = result['uom']
        if 'bom' in result:
            self.bom = result['bom']
        result.update(self.explode_bom())
        return result

    def on_change_with_uom_category(self, name=None):
        if self.product:
            return self.product.default_uom.category.id

    def on_change_with_unit_digits(self, name=None):
        if self.uom:
            return self.uom.digits
        return 2

    def on_change_bom(self):
        return self.explode_bom()

    def on_change_uom(self):
        return self.explode_bom()

    def on_change_quantity(self):
        return self.explode_bom()

    def get_cost(self, name):
        cost = Decimal(0)
        for input_ in self.inputs:
            if input_.cost_price is not None:
                cost_price = input_.cost_price
            else:
                cost_price = input_.product.cost_price
            cost += (Decimal(str(input_.internal_quantity)) * cost_price)
        return cost

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
        Template = pool.get('product.template')
        Product = pool.get('product.product')

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
                cost += Decimal(str(quantity)) * product.cost_price

        if hasattr(Product, 'cost_price'):
            digits = Product.cost_price.digits
        else:
            digits = Template.cost_price.digits

        for output in self.bom.outputs:
            quantity = output.compute_quantity(factor)
            product = output.product
            move = self._move(location, storage_location, company,
                product, output.uom, quantity)
            if move:
                move.production_output = self
                if product == self.product:
                    move.unit_price = Decimal(
                        cost / Decimal(str(quantity))
                        ).quantize(Decimal(str(10 ** -digits[1])))
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
            self.raise_user_error('missing_cost', (self.rec_name,))

    @classmethod
    def create(cls, vlist):
        Sequence = Pool().get('ir.sequence')
        Config = Pool().get('production.configuration')

        vlist = [x.copy() for x in vlist]
        config = Config(1)
        for values in vlist:
            values['code'] = Sequence.get_id(config.production_sequence.id)
        productions = super(Production, cls).create(vlist)
        for production in productions:
            production._set_move_planned_date()
        return productions

    @classmethod
    def write(cls, productions, values):
        super(Production, cls).write(productions, values)
        for production in productions:
            production._set_move_planned_date()

    def _get_move_planned_date(self):
        "Return the planned dates for input and output moves"
        return self.planned_date, self.planned_date

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
        Move.do([m for p in productions for m in p.inputs])

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def done(cls, productions):
        pool = Pool()
        Move = pool.get('stock.move')
        Date = pool.get('ir.date')
        Move.do([m for p in productions for m in p.outputs])
        cls.write(productions, {
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
            Button('Ok', 'end', 'tryton-ok', True),
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
