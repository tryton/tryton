#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
from functools import reduce, partial
from trytond.model import Workflow, ModelView, ModelSQL, fields
from trytond.backend import TableHandler
from trytond.pyson import In, Eval, Not, Equal, If, Get, Bool
from trytond.transaction import Transaction
from trytond.pool import Pool

__all__ = ['Move']

STATES = {
    'readonly': In(Eval('state'), ['cancel', 'assigned', 'done']),
}
DEPENDS = ['state']


class Move(Workflow, ModelSQL, ModelView):
    "Stock Move"
    __name__ = 'stock.move'
    _order_name = 'product'
    product = fields.Many2One("product.product", "Product", required=True,
        select=True, states=STATES,
        on_change=['product', 'currency', 'uom', 'company',
            'from_location', 'to_location'],
        domain=[('type', '!=', 'service')],
        depends=DEPENDS)
    product_uom_category = fields.Function(
        fields.Many2One('product.uom.category', 'Product Uom Category',
            on_change_with=['product']),
        'on_change_with_product_uom_category')
    uom = fields.Many2One("product.uom", "Uom", required=True, states=STATES,
        domain=[
            ('category', '=', Eval('product_uom_category')),
            ],
        on_change=['product', 'currency', 'uom', 'company',
            'from_location', 'to_location'],
        depends=['state', 'product_uom_category'])
    unit_digits = fields.Function(fields.Integer('Unit Digits',
        on_change_with=['uom']), 'on_change_with_unit_digits')
    quantity = fields.Float("Quantity", required=True,
        digits=(16, Eval('unit_digits', 2)), states=STATES,
        depends=['state', 'unit_digits'])
    internal_quantity = fields.Float('Internal Quantity', readonly=True,
        required=True)
    from_location = fields.Many2One("stock.location", "From Location",
        select=True, required=True, states=STATES, depends=DEPENDS,
        domain=[('type', 'not in', ('warehouse', 'view'))])
    to_location = fields.Many2One("stock.location", "To Location", select=True,
        required=True, states=STATES, depends=DEPENDS,
        domain=[('type', 'not in', ('warehouse', 'view'))])
    shipment = fields.Reference('Shipment', selection='get_shipment',
        readonly=True, select=True)
    origin = fields.Reference('Origin', selection='get_origin', select=True,
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])
    planned_date = fields.Date("Planned Date", states={
            'readonly': (In(Eval('state'), ['cancel', 'assigned', 'done'])
                | Eval('shipment'))
            }, depends=['state', 'shipment'],
        select=True)
    effective_date = fields.Date("Effective Date", readonly=True, select=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('assigned', 'Assigned'),
        ('done', 'Done'),
        ('cancel', 'Canceled'),
        ], 'State', select=True, readonly=True)
    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            },
        domain=[
            ('id', If(In('company', Eval('context', {})), '=', '!='),
                Get(Eval('context', {}), 'company', 0)),
            ],
        depends=['state'])
    unit_price = fields.Numeric('Unit Price', digits=(16, 4),
        states={
            'invisible': Not(Bool(Eval('unit_price_required'))),
            'required': Bool(Eval('unit_price_required')),
            'readonly': Not(Equal(Eval('state'), 'draft')),
            },
        depends=['unit_price_required', 'state'])
    cost_price = fields.Numeric('Cost Price', digits=(16, 4), readonly=True)
    currency = fields.Many2One('currency.currency', 'Currency',
        states={
            'invisible': Not(Bool(Eval('unit_price_required'))),
            'required': Bool(Eval('unit_price_required')),
            'readonly': Not(Equal(Eval('state'), 'draft')),
            },
        depends=['unit_price_required', 'state'])
    unit_price_required = fields.Function(fields.Boolean('Unit Price Required',
        on_change_with=['from_location', 'to_location']),
        'on_change_with_unit_price_required')

    @classmethod
    def __setup__(cls):
        super(Move, cls).__setup__()
        cls._sql_constraints += [
            ('check_move_qty_pos',
                'CHECK(quantity >= 0.0)', 'Move quantity must be positive'),
            ('check_move_internal_qty_pos',
                'CHECK(internal_quantity >= 0.0)',
                'Internal move quantity must be positive'),
            ('check_from_to_locations',
                'CHECK(from_location != to_location)',
                'Source and destination location must be different'),
            ]
        cls._order[0] = ('id', 'DESC')
        cls._error_messages.update({
            'set_state_draft': ('You can not set stock move "%s" to draft '
                'state.'),
            'set_state_assigned': ('You can not set stock move "%s" to '
                'assigned state.'),
            'set_state_done': 'You can not set stock move "%s" to done state.',
            'del_draft_cancel': ('You can not delete stock move "%s" because '
                'it is not in draft or cancelled state.'),
            'period_closed': ('You can not modify move "%(move)s" because '
                'period "%(period)s" is closed.'),
            'modify_assigned_done_cancel': ('You can not modify stock move "%s"'
                'because it is in "Assigned", "Done" or "Cancel" state.'),
            })
        cls._transitions |= set((
                ('draft', 'assigned'),
                ('draft', 'done'),
                ('draft', 'cancel'),
                ('assigned', 'draft'),
                ('assigned', 'done'),
                ('assigned', 'cancel'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': ~Eval('state').in_(['draft', 'assigned']),
                    },
                'draft': {
                    'invisible': ~Eval('state').in_(['assigned']),
                    },
                'assign': {
                    'invisible': ~Eval('state').in_(['assigned']),
                    },
                'do': {
                    'invisible': ~Eval('state').in_(['draft', 'assigned']),
                    },
                })

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        # Migration from 1.2: packing renamed into shipment
        table = TableHandler(cursor, cls, module_name)
        table.drop_constraint('check_packing')
        for suffix in ('in', 'out', 'in_return', 'out_return', 'internal'):
            old_column = 'packing_%s' % suffix
            new_column = 'shipment_%s' % suffix
            if table.column_exist(old_column):
                table.index_action(old_column, action='remove')
            table.drop_fk(old_column)
            table.column_rename(old_column, new_column)

        # Migration from 1.8: new field internal_quantity
        internal_quantity_exist = table.column_exist('internal_quantity')

        super(Move, cls).__register__(module_name)

        # Migration from 1.8: fill new field internal_quantity
        if not internal_quantity_exist:
            offset = 0
            limit = cursor.IN_MAX
            moves = True
            while moves:
                moves = cls.search([], offset=offset, limit=limit)
                offset += limit
                for move in moves:
                    internal_quantity = cls._get_internal_quantity(
                            move.quantity, move.uom, move.product)
                    cursor.execute(
                        'UPDATE "' + cls._table + '" '
                        'SET internal_quantity = %s '
                        'WHERE id = %s', (internal_quantity, move.id))
            table = TableHandler(cursor, cls, module_name)
            table.not_null_action('internal_quantity', action='add')

        # Migration from 1.0 check_packing_in_out has been removed
        table = TableHandler(cursor, cls, module_name)
        table.drop_constraint('check_packing_in_out')

        # Migration from 2.6: merge all shipments
        table.drop_constraint('check_shipment')
        shipments = {
            'shipment_in': 'stock.shipment.in',
            'shipment_out': 'stock.shipment.out',
            'shipment_out_return': 'stock.shipment.out.return',
            'shipment_in_return': 'stock.shipment.in.return',
            'shipment_internal': 'stock.shipment.internal',
            }
        for column, model in shipments.iteritems():
            if table.column_exist(column):
                cursor.execute('UPDATE "' + cls._table + '" '
                    'SET shipment = \'' + model + ',\' || "' + column + '" '
                    'WHERE "' + column + '" IS NOT NULL')
                table.drop_column(column)

        # Add index on create_date
        table.index_action('create_date', action='add')

    @staticmethod
    def default_planned_date():
        return Transaction().context.get('planned_date')

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_currency():
        Company = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            company = Company(company)
            return company.currency.id

    @staticmethod
    def default_unit_digits():
        return 2

    def on_change_with_unit_digits(self, name=None):
        if self.uom:
            return self.uom.digits
        return 2

    def on_change_product(self):
        pool = Pool()
        Uom = pool.get('product.uom')
        Currency = pool.get('currency.currency')

        res = {
            'unit_price': Decimal('0.0'),
            }
        if self.product:
            res['uom'] = self.product.default_uom.id
            res['uom.rec_name'] = self.product.default_uom.rec_name
            res['unit_digits'] = self.product.default_uom.digits
            unit_price = None
            if self.from_location and self.from_location.type in ('supplier',
                    'production'):
                unit_price = self.product.cost_price
            elif self.to_location and self.to_location.type == 'customer':
                unit_price = self.product.list_price
            if unit_price:
                if self.uom != self.product.default_uom:
                    unit_price = Uom.compute_price(self.product.default_uom,
                        unit_price, self.uom)
                if self.currency and self.company:
                    unit_price = Currency.compute(self.company.currency,
                        unit_price, self.currency, round=False)
                res['unit_price'] = unit_price
        return res

    def on_change_with_product_uom_category(self, name=None):
        if self.product:
            return self.product.default_uom_category.id

    def on_change_uom(self):
        pool = Pool()
        Uom = pool.get('product.uom')
        Currency = pool.get('currency.currency')

        res = {
            'unit_price': Decimal('0.0'),
            }
        if self.product:
            if self.to_location and self.to_location.type == 'storage':
                unit_price = self.product.cost_price
                if self.uom and self.uom != self.product.default_uom:
                    unit_price = Uom.compute_price(self.product.default_uom,
                        unit_price, self.uom)
                if self.currency and self.company:
                    unit_price = Currency.compute(self.company.currency,
                        unit_price, self.currency, round=False)
                res['unit_price'] = unit_price
        return res

    def on_change_with_unit_price_required(self, name=None):
        if (self.from_location
                and self.from_location.type in ('supplier', 'production')):
            return True
        if (self.to_location
                and self.to_location.type == 'customer'):
            return True
        return False

    @staticmethod
    def _get_shipment():
        'Return list of Model names for shipment Reference'
        return [
            'stock.shipment.in',
            'stock.shipment.out',
            'stock.shipment.out.return',
            'stock.shipment.in.return',
            'stock.shipment.internal',
            ]

    @classmethod
    def get_shipment(cls):
        Model = Pool().get('ir.model')
        models = cls._get_shipment()
        models = Model.search([
                ('model', 'in', models),
                ])
        return [(None, '')] + [(m.model, m.name) for m in models]

    @staticmethod
    def _get_origin():
        'Return list of Model names for origin Reference'
        return []

    @classmethod
    def get_origin(cls):
        Model = Pool().get('ir.model')
        models = cls._get_origin()
        models = Model.search([
                ('model', 'in', models),
                ])
        return [(None, '')] + [(m.model, m.name) for m in models]

    @classmethod
    def validate(cls, moves):
        super(Move, cls).validate(moves)
        cls.check_period_closed(moves)

    @classmethod
    def check_period_closed(cls, moves):
        Period = Pool().get('stock.period')
        periods = Period.search([
                ('state', '=', 'closed'),
                ], order=[('date', 'DESC')], limit=1)
        if periods:
            period, = periods
            for move in moves:
                date = (move.effective_date if move.effective_date
                    else move.planned_date)
                if date and date < period.date:
                    cls.raise_user_error('period_closed', {
                            'move': move.rec_name,
                            'period': period.rec_name,
                            })

    def get_rec_name(self, name):
        return ("%s%s %s"
            % (self.quantity, self.uom.symbol, self.product.rec_name))

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('product',) + clause[1:]]

    def _update_product_cost_price(self, direction):
        """
        Update the cost price on the given product.
        The direction must be "in" if incoming and "out" if outgoing.
        """
        pool = Pool()
        Uom = pool.get('product.uom')
        Product = pool.get('product.product')
        ProductTemplate = pool.get('product.template')
        Location = pool.get('stock.location')
        Currency = pool.get('currency.currency')
        Date = pool.get('ir.date')

        if direction == 'in':
            quantity = self.quantity
        elif direction == 'out':
            quantity = -self.quantity
        context = {}
        locations = Location.search([
                ('type', '=', 'storage'),
                ])
        context['locations'] = [l.id for l in locations]
        context['stock_date_end'] = Date.today()
        with Transaction().set_context(context):
            product = Product(self.product.id)
        qty = Uom.compute_qty(self.uom, quantity, product.default_uom)

        qty = Decimal(str(qty))
        if hasattr(Product, 'cost_price'):
            product_qty = product.quantity
        else:
            product_qty = product.template.quantity
        product_qty = Decimal(str(product_qty))
        # convert wrt currency
        with Transaction().set_context(date=self.effective_date):
            unit_price = Currency.compute(self.currency, self.unit_price,
                self.company.currency, round=False)
        # convert wrt to the uom
        unit_price = Uom.compute_price(self.uom, unit_price,
            product.default_uom)
        if product_qty + qty != Decimal('0.0'):
            new_cost_price = (
                (product.cost_price * product_qty) + (unit_price * qty)
                ) / (product_qty + qty)
        else:
            new_cost_price = product.cost_price

        if hasattr(Product, 'cost_price'):
            digits = Product.cost_price.digits
            write = partial(Product.write, [product])
        else:
            digits = ProductTemplate.cost_price.digits
            write = partial(ProductTemplate.write, [product.template])
        new_cost_price = new_cost_price.quantize(
            Decimal(str(10.0 ** -digits[1])))

        with Transaction().set_user(0, set_context=True):
            write({
                    'cost_price': new_cost_price,
                    })

    @staticmethod
    def _get_internal_quantity(quantity, uom, product):
        Uom = Pool().get('product.uom')
        internal_quantity = Uom.compute_qty(uom, quantity,
            product.default_uom, round=True)
        return internal_quantity

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, moves):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('assigned')
    def assign(cls, moves):
        pool = Pool()
        Date = pool.get('ir.date')

        today = Date.today()
        for move in moves:
            if not move.effective_date:
                move.effective_date = today
            move.save()

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def do(cls, moves):
        pool = Pool()
        Date = pool.get('ir.date')

        today = Date.today()
        for move in moves:
            if not move.effective_date:
                move.effective_date = today
            if (move.from_location.type in ('supplier', 'production')
                    and move.to_location.type == 'storage'
                    and move.product.cost_price_method == 'average'):
                move._update_product_cost_price('in')
            elif (move.to_location.type == 'supplier'
                    and move.from_location.type == 'storage'
                    and move.product.cost_price_method == 'average'):
                move._update_product_cost_price('out')
            if not move.cost_price:
                move.cost_price = move.product.cost_price
            move.save()

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, moves):
        pool = Pool()
        Date = pool.get('ir.date')

        today = Date.today()
        for move in moves:
            move.effective_date = today
            if (move.from_location.type in ('supplier', 'production')
                    and move.to_location.type == 'storage'
                    and move.product.cost_price_method == 'average'):
                move._update_product_cost_price('out')
            elif (move.to_location.type == 'supplier'
                    and move.from_location.type == 'storage'
                    and move.product.cost_price_method == 'average'):
                move._update_product_cost_price('in')
            move.effective_date = None
            move.save()

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Product = pool.get('product.product')
        Uom = pool.get('product.uom')

        vlist = [x.copy() for x in vlist]
        for vals in vlist:
            assert vals.get('state', 'draft') == 'draft'

            product = Product(vals['product'])
            uom = Uom(vals['uom'])
            internal_quantity = cls._get_internal_quantity(vals['quantity'],
                uom, product)
            vals['internal_quantity'] = internal_quantity
        return super(Move, cls).create(vlist)

    @classmethod
    def write(cls, moves, vals):
        if reduce(lambda x, y: x or y in vals, ('product', 'uom', 'quantity',
                'from_location', 'to_location', 'company', 'unit_price',
                'currency'), False):
            for move in moves:
                if move.state in ('assigned', 'done', 'cancel'):
                    cls.raise_user_error('modify_assigned_done_cancel',
                        (move.rec_name,))
        if reduce(lambda x, y: x or y in vals,
                ('planned_date', 'effective_date', 'state'), False):
            for move in moves:
                if move.state in ('done', 'cancel'):
                    cls.raise_user_error('modify_assigned_done_cancel',
                        (move.rec_name,))

        super(Move, cls).write(moves, vals)

        for move in moves:
            internal_quantity = cls._get_internal_quantity(move.quantity,
                    move.uom, move.product)
            if internal_quantity != move.internal_quantity:
                cls.write([move], {
                        'internal_quantity': internal_quantity,
                        })

    @classmethod
    def delete(cls, moves):
        for move in moves:
            if move.state not in ('draft', 'cancel'):
                cls.raise_user_error('del_draft_cancel', (move.rec_name,))
        super(Move, cls).delete(moves)

    def pick_product(self, location_quantities):
        """
        Pick the product across the location. Naive (fast) implementation.
        Return a list of tuple (location, quantity) for quantities that can be
        picked.
        """
        to_pick = []
        needed_qty = self.quantity
        for location, available_qty in location_quantities.iteritems():
            # Ignore available_qty when too small
            if available_qty < self.uom.rounding:
                continue
            if needed_qty <= available_qty:
                to_pick.append((location, needed_qty))
                return to_pick
            else:
                to_pick.append((location, available_qty))
                needed_qty -= available_qty
        # Force assignation for consumables:
        if self.product.consumable:
            to_pick.append((self.from_location, needed_qty))
            return to_pick
        return to_pick

    @classmethod
    def assign_try(cls, moves):
        '''
        Try to assign moves.
        It will split the moves to assign as much possible.
        Return True if succeed or False if not.
        '''
        pool = Pool()
        Product = pool.get('product.product')
        Uom = pool.get('product.uom')
        Date = pool.get('ir.date')
        Location = pool.get('stock.location')

        Transaction().cursor.lock(cls._table)

        locations = Location.search([
                ('parent', 'child_of', [x.from_location.id for x in moves]),
                ])
        with Transaction().set_context(
                stock_date_end=Date.today(),
                stock_assign=True):
            pbl = Product.products_by_location(
                location_ids=[l.id for l in locations],
                product_ids=[m.product.id for m in moves])

        success = True
        for move in moves:
            if move.state != 'draft':
                continue
            to_location = move.to_location
            location_qties = {}
            childs = Location.search([
                    ('parent', 'child_of', [move.from_location.id]),
                    ])
            for location in childs:
                if (location.id, move.product.id) in pbl:
                    location_qties[location] = Uom.compute_qty(
                            move.product.default_uom,
                            pbl[(location.id, move.product.id)], move.uom,
                            round=False)

            to_pick = move.pick_product(location_qties)

            picked_qties = 0.0
            for _, qty in to_pick:
                picked_qties += qty

            if picked_qties < move.quantity:
                success = False
                first = False
                cls.write([move], {
                    'quantity': move.quantity - picked_qties,
                    })
            else:
                first = True
            for from_location, qty in to_pick:
                values = {
                    'from_location': from_location.id,
                    'quantity': qty,
                    }
                if first:
                    cls.write([move], values)
                    cls.assign([move])
                    first = False
                else:
                    cls.assign(cls.copy([move], default=values))

                qty_default_uom = Uom.compute_qty(move.uom, qty,
                        move.product.default_uom, round=False)

                pbl[(from_location.id, move.product.id)] = (
                    pbl.get((from_location.id, move.product.id), 0.0)
                    - qty_default_uom)
                pbl[(to_location.id, move.product.id)] = (
                    pbl.get((to_location.id, move.product.id), 0.0)
                    + qty_default_uom)
        return success
