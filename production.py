#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.model import ModelView, ModelSQL, Workflow, fields
from trytond.wizard import Wizard, StateTransition, StateView, Button
from trytond.pyson import Eval, Bool, If, Id
from trytond.pool import Pool
from trytond.transaction import Transaction

BOM_CHANGES = ['bom', 'product', 'quantity', 'uom', 'warehouse', 'location',
    'company', 'inputs', 'outputs']


class Production(Workflow, ModelSQL, ModelView):
    "Production"
    _name = 'production'
    _description = __doc__
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
            'required': Bool(Eval('product')),
            'invisible': ~Eval('product'),
            },
        on_change=BOM_CHANGES,
        depends=['product'])
    uom_category = fields.Function(fields.Many2One(
            'product.uom.category', 'Uom Category',
            on_change_with=['product']), 'get_uom_category')
    uom = fields.Many2One('product.uom', 'Uom',
        domain=[
            ('category', '=', Eval('uom_category')),
            ],
        states={
            'readonly': ~Eval('state').in_(['request', 'draft']),
            'required': Bool(Eval('bom')),
            'invisible': ~Eval('bom'),
            },
        on_change=BOM_CHANGES,
        depends=['uom_category'])
    unit_digits = fields.Function(fields.Integer('Unit Digits',
            on_change_with=['uom']), 'get_unit_digits')
    quantity = fields.Float('Quantity',
        digits=(16, Eval('unit_digits', 2)),
        states={
            'readonly': ~Eval('state').in_(['request', 'draft']),
            'required': Bool(Eval('bom')),
            'invisible': ~Eval('bom'),
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

    def __init__(self):
        super(Production, self).__init__()
        self._constraints += [
            ('check_cost', 'missing_cost'),
            ]
        self._error_messages.update({
                'missing_cost': 'It misses some cost on the outputs!',
                })
        self._transitions |= set((
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
        self._buttons.update({
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
                'assign_try': {},
                'assign_force': {},
                })

    def default_state(self):
        return 'draft'

    def default_warehouse(self):
        location_obj = Pool().get('stock.location')
        location_ids = location_obj.search(self.warehouse.domain)
        if len(location_ids) == 1:
            return location_ids[0]

    def default_location(self):
        location_obj = Pool().get('stock.location')
        warehouse_id = self.default_warehouse()
        if warehouse_id:
            warehouse = location_obj.browse(warehouse_id)
            return warehouse.production_location.id

    def default_company(self):
        return Transaction().context.get('company')

    def _move_values(self, from_location, to_location, company, product, uom,
            quantity):
        values = {
            'product': product.id,
            'uom': uom.id,
            'quantity': quantity,
            'from_location': None,
            'to_location': None,
            'company': None,
            'state': 'draft',
            }
        values['currency'] = company.currency.id if company else None
        if from_location:
            values['from_location'] = from_location.id
        if to_location:
            values['to_location'] = to_location.id
        if company:
            values['company'] = company.id
        return values

    def _explode_move_values(self, from_location, to_location, company,
            bom_io, quantity):
        pool = Pool()
        move_obj = pool.get('stock.move')

        values = self._move_values(from_location, to_location, company,
            bom_io.product, bom_io.uom, quantity)
        values['product.rec_name'] = bom_io.product.rec_name
        values['uom.rec_name'] = bom_io.uom.rec_name
        values['unit_price_required'] = \
            move_obj.on_change_with_unit_price_required({
                    'from_location': (from_location.id if from_location else
                        None),
                    'to_location': to_location.id if to_location else None,
                    })
        if from_location:
            values['from_location.rec_name'] = from_location.rec_name
        if to_location:
            values['to_location.rec_name'] = to_location.rec_name
        if company:
            values['company.rec_name'] = company.rec_name
        return values

    def explode_bom(self, values):
        pool = Pool()
        bom_obj = pool.get('production.bom')
        product_obj = pool.get('product.product')
        uom_obj = pool.get('product.uom')
        input_obj = pool.get('production.bom.input')
        output_obj = pool.get('production.bom.output')
        location_obj = pool.get('stock.location')
        company_obj = pool.get('company.company')

        if not (values.get('bom')
                and values.get('product')
                and values.get('uom')):
            return {}
        inputs = {
            'remove': [r['id'] for r in values.get('inputs') or []],
            'add': [],
            }
        outputs = {
            'remove': [r['id'] for r in values.get('outputs') or []],
            'add': [],
            }
        changes = {
            'inputs': inputs,
            'outputs': outputs,
            'cost': Decimal(0),
            }

        bom = bom_obj.browse(values['bom'])
        product = product_obj.browse(values['product'])
        quantity = values.get('quantity') or 0
        uom = uom_obj.browse(values['uom'])
        if values.get('warehouse'):
            warehouse = location_obj.browse(values['warehouse'])
            storage_location = warehouse.storage_location
        else:
            storage_location = None
        if values.get('location'):
            location = location_obj.browse(values['location'])
        else:
            location = None
        if values.get('company'):
            company = company_obj.browse(values['company'])
        else:
            company = None

        factor = bom_obj.compute_factor(bom, product, quantity, uom)
        for input_ in bom.inputs:
            quantity = input_obj.compute_quantity(input_, factor)
            values = self._explode_move_values(storage_location, location,
                company, input_, quantity)
            if values:
                inputs['add'].append(values)
                quantity = uom_obj.compute_qty(input_.uom, quantity,
                    input_.product.default_uom)
                changes['cost'] += (Decimal(str(quantity)) *
                    input_.product.cost_price)

        for output in bom.outputs:
            quantity = output_obj.compute_quantity(output, factor)
            values = self._explode_move_values(location, storage_location,
                company, output, quantity)
            if values:
                values['unit_price'] = Decimal(0)
                if output.product.id == values.get('product') and quantity:
                    values['unit_price'] = (changes['cost'] /
                        Decimal(str(quantity)))
                outputs['add'].append(values)
        return changes

    def on_change_warehouse(self, values):
        location_obj = Pool().get('stock.location')
        changes = {
            'location': None,
            }
        if values.get('warehouse'):
            warehouse = location_obj.browse(values['warehouse'])
            changes['location'] = warehouse.production_location.id
        return changes

    def on_change_product(self, values):
        product_obj = Pool().get('product.product')

        result = {}
        if values.get('product'):
            product = product_obj.browse(values['product'])
            uom_ids = [x.id for x in product.default_uom.category.uoms]
            if (not values.get('uom')
                    or values.get('uom') not in uom_ids):
                result['uom'] = product.default_uom.id
                result['uom.rec_name'] = product.default_uom.rec_name
                result['unit_digits'] = product.default_uom.digits
        else:
            result['bom'] = None
            result['uom'] = None
            result['uom.rec_name'] = ''
            result['unit_digits'] = 2

        values = values.copy()
        values['uom'] = result['uom']
        if 'bom' in result:
            values['bom'] = result['bom']
        result.update(self.explode_bom(values))
        return result

    def on_change_with_uom_category(self, values):
        product_obj = Pool().get('product.product')
        if values.get('product'):
            product = product_obj.browse(values['product'])
            return product.default_uom.category.id

    def get_uom_category(self, ids, name):
        res = {}
        for production in self.browse(ids):
            if production.product:
                res[production.id] = production.product.default_uom.category.id
            else:
                res[production.id] = None
        return res

    def on_change_with_unit_digits(self, values):
        uom_obj = Pool().get('product.uom')
        if values.get('uom'):
            uom = uom_obj.browse(values['uom'])
            return uom.digits
        return 2

    def get_unit_digits(self, ids, name):
        digits = {}
        for production in self.browse(ids):
            if production.uom:
                digits[production.id] = production.uom.digits
            else:
                digits[production.id] = 2
        return digits

    def on_change_bom(self, values):
        return self.explode_bom(values)

    def on_change_uom(self, values):
        return self.explode_bom(values)

    def on_change_quantity(self, values):
        return self.explode_bom(values)

    def get_cost(self, ids, name):
        costs = {}
        for production in self.browse(ids):
            costs[production.id] = Decimal(0)
            for input_ in production.inputs:
                if input_.cost_price is not None:
                    cost_price = input_.cost_price
                else:
                    cost_price = input_.product.cost_price
                costs[production.id] += (Decimal(str(input_.internal_quantity))
                        * cost_price)
        return costs

    def on_change_with_cost(self, values):
        pool = Pool()
        product_obj = pool.get('product.product')
        uom_obj = pool.get('product.uom')

        cost = Decimal(0)
        if not values.get('inputs'):
            return cost

        product_ids = list(set(r['product'] for r in values['inputs'] if
                r['product'] is not None))
        id2product = dict((p.id, p) for p in product_obj.browse(product_ids))

        uom_ids = list(set(r['uom'] for r in values['inputs']))
        id2uom = dict((u.id, u) for u in uom_obj.browse(uom_ids))

        for input_ in values['inputs']:
            if (input_['product'] is None
                    or input_['uom'] is None
                    or input_['quantity'] is None):
                continue
            product = id2product[input_['product']]
            quantity = uom_obj.compute_qty(id2uom[input_['uom']],
                input_['quantity'], product.default_uom)
            cost += Decimal(str(quantity)) * product.cost_price
        return cost

    def set_moves(self, production):
        pool = Pool()
        bom_obj = pool.get('production.bom')
        move_obj = pool.get('stock.move')
        input_obj = pool.get('production.bom.input')
        output_obj = pool.get('production.bom.output')

        storage_location = production.warehouse.storage_location
        location = production.location
        company = production.company

        if not production.bom:
            if production.product:
                product = production.product
                values = self._move_values(location, storage_location, company,
                    product, product.default_uom)
                if values:
                    values['production_output'] = production.id
                    move_obj.create(values)
            return

        factor = bom_obj.compute_factor(production.bom, production.product,
            production.quantity, production.uom)
        cost = Decimal(0)
        for input_ in production.bom.inputs:
            quantity = input_obj.compute_quantity(input_, factor)
            product = input_.product
            values = self._move_values(storage_location, location, company,
                product, input_.uom, quantity)
            if values:
                values['production_input'] = production.id
                move_obj.create(values)
                cost += Decimal(str(quantity)) * product.cost_price

        for output in production.bom.outputs:
            quantity = output_obj.compute_quantity(output, factor)
            product = output.product
            values = self._move_values(location, storage_location, company,
                product, output.uom, quantity)
            if values:
                values['production_output'] = production.id
                if product == production.product:
                    values['unit_price'] = cost / Decimal(str(quantity))
                move_obj.create(values)
        self._set_move_planned_date([production.id])

    def check_cost(self, ids):
        pool = Pool()
        currency_obj = pool.get('currency.currency')

        for production in self.browse(ids):
            if production.state != 'done':
                continue
            cost_price = Decimal(0)
            for output in production.outputs:
                cost_price += (Decimal(str(output.quantity))
                    * output.unit_price)
            if not currency_obj.is_zero(production.company.currency,
                    production.cost - cost_price):
                return False
        return True

    def create(self, values):
        sequence_obj = Pool().get('ir.sequence')
        config_obj = Pool().get('production.configuration')

        values = values.copy()
        config = config_obj.browse(1)
        values['code'] = sequence_obj.get_id(config.production_sequence.id)
        production_id = super(Production, self).create(values)
        self._set_move_planned_date(production_id)
        return production_id

    def write(self, ids, values):
        result = super(Production, self).write(ids, values)
        self._set_move_planned_date(ids)
        return result

    def _get_move_planned_date(self, production):
        "Return the planned dates for input and output moves"
        return production.planned_date, production.planned_date

    def _set_move_planned_date(self, ids):
        "Set planned date of moves for the shipments"
        pool = Pool()
        move_obj = pool.get('stock.move')
        if isinstance(ids, (int, long)):
            ids = [ids]
        for production in self.browse(ids):
            dates = self._get_move_planned_date(production)
            input_date, output_date = dates
            move_obj.write([m.id for m in production.inputs
                    if m.state not in ('assigned', 'done', 'cancel')], {
                    'planned_date': input_date,
                    })
            move_obj.write([m.id for m in production.outputs
                    if m.state not in ('assigned', 'done', 'cancel')], {
                    'planned_date': output_date,
                    })

    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(self, ids):
        pool = Pool()
        move_obj = pool.get('stock.move')
        productions = self.browse(ids)
        move_obj.write([m.id for p in productions
                for m in p.inputs + p.outputs
                if m.state != 'cancel'], {
                'state': 'cancel',
                })

    @ModelView.button
    @Workflow.transition('draft')
    def draft(self, ids):
        pool = Pool()
        move_obj = pool.get('stock.move')
        productions = self.browse(ids)
        move_obj.write([m.id for p in productions
                for m in p.inputs + p.outputs
                if m.state != 'draft'], {
                'state': 'draft',
                })

    @ModelView.button
    @Workflow.transition('waiting')
    def wait(self, ids):
        pool = Pool()
        move_obj = pool.get('stock.move')
        productions = self.browse(ids)
        move_obj.write([m.id for p in productions
                for m in p.inputs + p.outputs
                if m.state not in ('draft', 'done')], {
                'state': 'draft',
                })

    @Workflow.transition('assigned')
    def assign(self, ids):
        pass

    @ModelView.button
    @Workflow.transition('running')
    def run(self, ids):
        pool = Pool()
        move_obj = pool.get('stock.move')
        productions = self.browse(ids)
        move_obj.write([m.id for p in productions
                for m in p.inputs
                if m.state not in ('done', 'cancel')], {
                'state': 'done',
                })

    @ModelView.button
    @Workflow.transition('done')
    def done(self, ids):
        pool = Pool()
        move_obj = pool.get('stock.move')
        date_obj = pool.get('ir.date')
        productions = self.browse(ids)
        move_obj.write([m.id for p in productions
                for m in p.outputs
                if m.state not in ('done', 'cancel')], {
                'state': 'done',
                })
        self.write(ids, {
                'effective_date': date_obj.today(),
                })

    @ModelView.button
    def assign_try(self, ids):
        pool = Pool()
        move_obj = pool.get('stock.move')
        productions = self.browse(ids)
        if move_obj.assign_try([m for p in productions
                    for m in p.inputs]):
            self.assign(ids)
            return True
        else:
            return False

    @ModelView.button
    def assign_force(self, ids):
        pool = Pool()
        move_obj = pool.get('stock.move')
        productions = self.browse(ids)
        move_obj.write([m.id for p in productions for m in p.inputs
                if m.state != 'done'], {
                'state': 'assigned',
                })
        self.assign(ids)

Production()


class AssignFailed(ModelView):
    'Assign Production'
    _name = 'production.assign.failed'
    _description = __doc__

    moves = fields.Many2Many('stock.move', None, None, 'Moves', readonly=True)

    def default_moves(self):
        pool = Pool()
        production_obj = pool.get('production')
        production_id = Transaction().context.get('active_id')
        if not production_id:
            return []
        production = production_obj.browse(production_id)
        return [m.id for m in production.inputs if m.state == 'draft']

AssignFailed()


class Assign(Wizard):
    'Assign Production'
    _name = 'production.assign'

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

    def transition_start(self, session):
        pool = Pool()
        production_obj = pool.get('production')

        if production_obj.assign_try([Transaction().context['active_id']]):
            return 'end'
        else:
            return 'failed'

    def transition_force(self, session):
        pool = Pool()
        production_obj = pool.get('production')

        production_obj.assign_force([Transaction().context['active_id']])
        return 'end'

Assign()
