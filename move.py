#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import datetime
import operator
from decimal import Decimal
from functools import partial
from sql import Literal, Union, Column
from sql.aggregate import Sum
from sql.conditionals import Coalesce
from sql.operators import Concat

from trytond.model import Workflow, Model, ModelView, ModelSQL, fields
from trytond import backend
from trytond.pyson import In, Eval, Not, Equal, If, Bool
from trytond.tools import reduce_ids
from trytond.transaction import Transaction
from trytond.pool import Pool

__all__ = ['StockMixin', 'Move']

STATES = {
    'readonly': In(Eval('state'), ['cancel', 'assigned', 'done']),
}
DEPENDS = ['state']


class StockMixin:
    '''Mixin class with helper to setup stock quantity field.'''

    @classmethod
    def _quantity_context(cls, name):
        pool = Pool()
        Date = pool.get('ir.date')

        context = Transaction().context
        new_context = {}
        if name == 'quantity':
            if (context.get('stock_date_end')
                    and context['stock_date_end'] > Date.today()):
                new_context['stock_date_end'] = Date.today()
        elif name == 'forecast_quantity':
            new_context['forecast'] = True
            if not context.get('stock_date_end'):
                new_context['stock_date_end'] = datetime.date.max
        return new_context

    @classmethod
    def _get_quantity(cls, records, name, location_ids, products=None,
            grouping=('product',), position=-1):
        """
        Compute for each record the stock quantity in the default uom of the
        product.

        location_ids is the list of IDs of locations to take account to compute
            the stock. It can't be empty.
        products restrict the stock computation to the this products (more
            efficient), so it should be the products related to records.
            If it is None all products are used.
        grouping defines how stock moves are grouped.
        position defines which field of grouping corresponds to the record
            whose quantity is computed.

        Return a dictionary with records id as key and quantity as value.
        """
        pool = Pool()
        Product = pool.get('product.product')

        record_ids = [r.id for r in records]
        quantities = dict.fromkeys(record_ids, 0.0)
        if not location_ids:
            return quantities

        product_ids = products and [p.id for p in products] or None

        with Transaction().set_context(cls._quantity_context(name)):
            pbl = Product.products_by_location(location_ids=location_ids,
                product_ids=product_ids, with_childs=True,
                grouping=grouping)

        for key, quantity in pbl.iteritems():
            # pbl could return None in some keys
            if (key[position] is not None and
                    key[position] in quantities):
                quantities[key[position]] += quantity
        return quantities

    @classmethod
    def _search_quantity(cls, name, location_ids, domain=None,
            grouping=('product',), position=-1):
        """
        Compute the domain to filter records which validates the domain over
        quantity field.

        The context with keys:
            stock_skip_warehouse: if set, quantities on a warehouse are no more
                quantities of all child locations but quantities of the storage
                zone.
        location_ids is the list of IDs of locations to take account to compute
            the stock. It can't be empty.
        grouping defines how stock moves are grouped.
        position defines which field of grouping corresponds to the record
            whose quantity is computed.
        """
        pool = Pool()
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')

        if not location_ids or not domain:
            return []

        # Skip warehouse location in favor of their storage location
        # to compute quantities. Keep track of which ids to remove
        # and to add after the query.
        if Transaction().context.get('stock_skip_warehouse'):
            location_ids = set(location_ids)
            for location in Location.browse(list(location_ids)):
                if location.type == 'warehouse':
                    location_ids.remove(location.id)
                    location_ids.add(location.storage_location.id)
            location_ids = list(location_ids)

        with Transaction().set_context(cls._quantity_context(name)):
            query = Move.compute_quantities_query(location_ids,
                with_childs=True, grouping=grouping,
                grouping_filter=None)
            having_domain = getattr(cls, name)._field.convert_domain(domain, {
                    None: (query, {}),
                    }, cls)
            # The last column of 'query' is always the quantity for the 'key'.
            # It is computed with a SUM() aggregator so in having we have to
            # use the SUM() expression and not the name of column
            having_domain.left = query.columns[-1].expression
            if query.having:
                query.having &= having_domain
            else:
                query.having = having_domain
            quantities = Move.compute_quantities(query, location_ids,
                with_childs=True, grouping=grouping,
                grouping_filter=None)

        record_ids = []
        for key, quantity in quantities.iteritems():
            # pbl could return None in some keys
            if key[position] is not None:
                record_ids.append(key[position])

        return [('id', 'in', record_ids)]


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
                Eval('context', {}).get('company', -1)),
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
        cls._deny_modify_assigned = set(['product', 'uom', 'quantity',
            'from_location', 'to_location', 'company', 'unit_price',
            'currency'])
        cls._deny_modify_done_cancel = (cls._deny_modify_assigned |
            set(['planned_date', 'effective_date', 'state']))
        cls._allow_modify_closed_period = set()

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
            'modify_assigned': ('You can not modify stock move "%s" because '
                'it is in "Assigned" state.'),
            'modify_done_cancel': ('You can not modify stock move "%s" '
                'because it is in "Done" or "Cancel" state.'),
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
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        sql_table = cls.__table__()

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
                    cursor.execute(*sql_table.update(
                            columns=[sql_table.internal_quantity],
                            values=[internal_quantity],
                            where=sql_table.id == move.id))
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
                cursor.execute(*sql_table.update(
                        columns=[sql_table.shipment],
                        values=[Concat(model + ',',
                                Column(sql_table, column))],
                        where=Column(sql_table, column) != None))
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
        if (self.from_location and self.to_location
                and self.from_location.type == 'storage'
                and self.to_location.type == 'supplier'):
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
        IrModel = Pool().get('ir.model')
        models = cls._get_shipment()
        models = IrModel.search([
                ('model', 'in', models),
                ])
        return [(None, '')] + [(m.model, m.name) for m in models]

    @staticmethod
    def _get_origin():
        'Return list of Model names for origin Reference'
        return ['stock.inventory.line']

    @classmethod
    def get_origin(cls):
        IrModel = Pool().get('ir.model')
        models = cls._get_origin()
        models = IrModel.search([
                ('model', 'in', models),
                ])
        return [(None, '')] + [(m.model, m.name) for m in models]

    @property
    def origin_name(self):
        return self.origin.rec_name if self.origin else None

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
        return [('product',) + tuple(clause[1:])]

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
        moves = super(Move, cls).create(vlist)
        cls.check_period_closed(moves)
        return moves

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        for moves, values in zip(actions, actions):
            vals_set = set(values)
            if cls._deny_modify_assigned & vals_set:
                for move in moves:
                    if move.state == 'assigned':
                        cls.raise_user_error('modify_assigned', move.rec_name)
            if cls._deny_modify_done_cancel & vals_set:
                for move in moves:
                    if move.state in ('done', 'cancel'):
                        cls.raise_user_error('modify_done_cancel',
                            (move.rec_name,))

            if any(f not in cls._allow_modify_closed_period for f in values):
                cls.check_period_closed(moves)

        super(Move, cls).write(*args)

        actions = iter(args)
        for moves, values in zip(actions, actions):
            for move in moves:
                internal_quantity = cls._get_internal_quantity(move.quantity,
                        move.uom, move.product)
                if (internal_quantity != move.internal_quantity
                        and internal_quantity
                        != values.get('internal_quantity')):
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
    def assign_try(cls, moves, with_childs=True, grouping=('product',)):
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

        if with_childs:
            locations = Location.search([
                    ('parent', 'child_of',
                        [x.from_location.id for x in moves]),
                    ])
        else:
            locations = list(set((m.from_location for m in moves)))
        with Transaction().set_context(
                stock_date_end=Date.today(),
                stock_assign=True):
            pbl = Product.products_by_location(
                location_ids=[l.id for l in locations],
                product_ids=[m.product.id for m in moves],
                grouping=grouping)

        def get_key(location):
            key = (location.id,)
            for field in grouping:
                value = getattr(move, field)
                if isinstance(value, Model):
                    value = value.id
                key += (value,)
            return key

        success = True
        for move in moves:
            if move.state != 'draft':
                continue
            to_location = move.to_location
            location_qties = {}
            if with_childs:
                childs = Location.search([
                        ('parent', 'child_of', [move.from_location.id]),
                        ])
            else:
                childs = [move.from_location]
            for location in childs:
                key = get_key(location)
                if key in pbl:
                    location_qties[location] = Uom.compute_qty(
                        move.product.default_uom, pbl[key], move.uom,
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

                from_key, to_key = get_key(from_location), get_key(to_location)
                pbl[from_key] = pbl.get(from_key, 0.0) - qty_default_uom
                pbl[to_key] = pbl.get(to_key, 0.0) + qty_default_uom
        return success

    @classmethod
    def compute_quantities_query(cls, location_ids, with_childs=False,
            grouping=('product',), grouping_filter=None):
        """
        Prepare a query object to compute for each location and product the
        stock quantity in the default uom of the product.

        The context with keys:
            stock_date_end: if set the date of the stock computation.
            stock_date_start: if set return the delta of the stock between the
                two dates, (ignored if stock_date_end is missing).
            stock_assign: if set compute also the assigned moves as done.
            forecast: if set compute the forecast quantity.
            stock_destinations: A list of location ids. If set, restrict the
                computation to moves from and to those locations.
            stock_skip_warehouse: if set, quantities on a warehouse are no more
                quantities of all child locations but quantities of the storage
                zone.
        If with_childs, it computes also for child locations.
        grouping is a tuple of Move field names and defines how stock moves are
            grouped.
        grouping_filter is a tuple of values, for the Move's field at the same
            position in grouping tuple, used to filter which moves are used to
            compute quantities. It must be None or have the same number of
            elements than grouping. If no grouping_filter is provided it
            returns quantities for all products.

        The query return the location as first column, after the fields in
            grouping, and the last column is the quantity.
        """
        pool = Pool()
        Rule = pool.get('ir.rule')
        Location = pool.get('stock.location')
        Date = pool.get('ir.date')
        Period = pool.get('stock.period')
        Move = pool.get('stock.move')
        Product = pool.get('product.product')
        Template = pool.get('product.template')

        move = Move.__table__()
        product = Product.__table__()
        template = Template.__table__()

        today = Date.today()

        if not location_ids:
            return None
        context = Transaction().context.copy()

        for field in grouping:
            if field not in Move._fields:
                raise ValueError('"%s" has no field "%s"' % (Move, field))
        assert grouping_filter is None or len(grouping_filter) == len(grouping)

        move_rule_query = Rule.domain_get('stock.move')
        if move_rule_query is None:
            move_rule_query = Literal(True)

        PeriodCache = Period.get_cache(grouping)
        period = None
        if PeriodCache:
            period_cache = PeriodCache.__table__()

        if not context.get('stock_date_end'):
            context['stock_date_end'] = datetime.date.max

        # date end in the past or today: filter on state done
        if (context['stock_date_end'] < today
                or (context['stock_date_end'] == today
                    and not context.get('forecast'))):
            state_date_clause = (
                move.state.in_(['done',
                        context.get('stock_assign') and 'assigned' or 'done'])
                & (
                    (
                        (move.effective_date == None)
                        & (move.planned_date <= context['stock_date_end'])
                        )
                    | (move.effective_date <= context['stock_date_end'])
                    )
                )
        # future date end: filter move on state done and date
        # before today, or on all state and date between today and
        # date_end.
        else:
            state_date_clause = (
                (move.state.in_(['done',
                            context.get('stock_assign') and 'assigned'
                            or 'done'])
                    & (
                        (
                            (move.effective_date == None)
                            & (move.planned_date <= today)
                            )
                        | (move.effective_date <= today)
                        )
                    )
                | (move.state.in_(['done', 'assigned', 'draft'])
                    & (
                        (
                            (move.effective_date == None)
                            & (Coalesce(move.planned_date, datetime.date.max)
                                <= context['stock_date_end'])
                            & (Coalesce(move.planned_date, datetime.date.max)
                                >= today)
                            )
                        | (
                            (move.effective_date <= context['stock_date_end'])
                            & (move.effective_date >= today)
                            )
                        )
                    )
                )

        if context.get('stock_date_start'):
            if context['stock_date_start'] > today:
                state_date_clause &= (
                    move.state.in_(['done', 'assigned', 'draft'])
                    & (
                        (
                            (move.effective_date == None)
                            & (
                                (move.planned_date >=
                                    context['stock_date_start'])
                                | (move.planned_date == None)
                                )
                            )
                        | (move.effective_date >= context['stock_date_start'])
                        )
                    )
            else:
                state_date_clause &= (
                    (
                        move.state.in_(['done', 'assigned', 'draft'])
                        & (
                            (
                                (move.effective_date == None)
                                & (
                                    (move.planned_date >= today)
                                    | (move.planned_date == None)
                                    )
                                )
                            | (move.effective_date >= today)
                            )
                        )
                    | (
                        move.state.in_(['done',
                                context.get('stock_assign') and 'assigned'
                                or 'done'])
                        & (
                            (
                                (move.effective_date == None)
                                & (
                                    (
                                        (move.planned_date >=
                                            context['stock_date_start'])
                                        & (move.planned_date < today)
                                        )
                                    | (move.planned_date == None)
                                    )
                                )
                            | (
                                (move.effective_date >=
                                    context['stock_date_start'])
                                & (move.effective_date < today)
                                )
                            )
                        )
                    )
        elif PeriodCache:
            with Transaction().set_user(0, set_context=True):
                periods = Period.search([
                        ('date', '<', context['stock_date_end']),
                        ('state', '=', 'closed'),
                        ], order=[('date', 'DESC')], limit=1)
            if periods:
                period, = periods
                state_date_clause &= (
                    Coalesce(move.effective_date, move.planned_date,
                        datetime.date.max) > period.date)

        if with_childs:
            location_query = Location.search([
                    ('parent', 'child_of', location_ids),
                    ], query=True, order=[])
        else:
            location_query = location_ids[:]

        from_ = move
        if PeriodCache:
            from_period = period_cache
        if grouping_filter and any(grouping_filter):
            where = where_period = Literal(True)
            for fieldname, grouping_ids in zip(grouping, grouping_filter):
                if not grouping_ids:
                    continue
                column = Column(move, fieldname)
                if PeriodCache:
                    cache_column = Column(period_cache, fieldname)
                if isinstance(grouping_ids[0], (int, long, float, Decimal)):
                    where &= reduce_ids(column, grouping_ids)
                    if PeriodCache:
                        where_period &= reduce_ids(cache_column, grouping_ids)
                else:
                    where &= column.in_(grouping_ids)
                    if PeriodCache:
                        where_period &= cache_column.in_(grouping_ids)
        else:
            where = where_period = template.active == True
            from_ = from_.join(product, condition=move.product == product.id)
            from_ = from_.join(template,
                condition=product.template == template.id)
            if PeriodCache:
                from_period = from_period.join(product,
                    condition=period_cache.product == product.id)
                from_period = from_period.join(template,
                    condition=product.template == template.id)

        if context.get('stock_destinations'):
            destinations = context['stock_destinations']
            dest_clause_from = move.from_location.in_(destinations)
            dest_clause_to = move.to_location.in_(destinations)

            if PeriodCache:
                dest_clause_period = period_cache.location.in_(destinations)

        else:
            dest_clause_from = dest_clause_to = dest_clause_period = \
                Literal(True)

        # The main select clause is a union between three similar subqueries.
        # One that sums incoming moves towards locations, one that sums
        # outgoing moves and one for the period cache.  UNION ALL is used
        # because we already know that there will be no duplicates.
        move_keys = [Column(move, key).as_(key) for key in grouping]
        query = from_.select(move.to_location.as_('location'),
            Sum(move.internal_quantity).as_('quantity'),
            *move_keys,
            where=state_date_clause
            & where
            & move.to_location.in_(location_query)
            & move.id.in_(move_rule_query)
            & dest_clause_from,
            group_by=[move.to_location] + move_keys)
        query = Union(query, from_.select(move.from_location.as_('location'),
                (-Sum(move.internal_quantity)).as_('quantity'),
                *move_keys,
                where=state_date_clause
                & where
                & move.from_location.in_(location_query)
                & move.id.in_(move_rule_query)
                & dest_clause_to,
                group_by=[move.from_location] + move_keys),
            all_=True)
        if PeriodCache:
            period_keys = [Column(period_cache, key).as_(key)
                for key in grouping]
            query = Union(query, from_period.select(
                    period_cache.location.as_('location'),
                    period_cache.internal_quantity.as_('quantity'),
                    *period_keys,
                    where=(period_cache.period
                        == (period.id if period else None))
                    & where_period
                    & period_cache.location.in_(location_query)
                    & dest_clause_period),
                all_=True)
        query_keys = [Column(query, key).as_(key) for key in grouping]
        columns = ([query.location.as_('location')]
            + query_keys
            + [Sum(query.quantity).as_('quantity')])
        query = query.select(*columns,
            group_by=[query.location] + query_keys)
        return query

    @classmethod
    def compute_quantities(cls, query, location_ids, with_childs=False,
            grouping=('product',), grouping_filter=None):
        """
        Executes the supplied query to compute for each location and product
        the stock quantity in the default uom of the product and rounded to
        Uom's rounding digits.

        See compute_quantites_query for params explanation.

        Return a dictionary with location id and grouping as key
            and quantity as value.
        """
        pool = Pool()
        Location = pool.get('stock.location')
        Product = pool.get('product.product')
        Uom = pool.get('product.uom')

        assert query is not None, (
            "Query in Move.compute_quantities() can't be None")
        assert 'product' in grouping

        cursor = Transaction().cursor
        cursor.execute(*query)
        raw_lines = cursor.fetchall()

        product_getter = operator.itemgetter(grouping.index('product') + 1)
        res_product_ids = set()
        quantities = {}
        keys = set()
        for line in raw_lines:
            location = line[0]
            key = tuple(line[1:-1])
            quantity = line[-1]
            quantities[(location,) + key] = quantity
            res_product_ids.add(product_getter(line))
            keys.add(key)

        # Propagate quantities on from child locations to their parents
        if with_childs:
            # Fetch all child locations
            locations = Location.search([
                    ('parent', 'child_of', location_ids),
                    ])
            # Generate a set of locations without childs and a dict
            # giving the parent of each location.
            leafs = set([l.id for l in locations])
            parent = {}
            for location in locations:
                if not location.parent:
                    continue
                if location.parent.id in leafs:
                    leafs.remove(location.parent.id)
                parent[location.id] = location.parent.id
            locations = set((l.id for l in locations))
            while leafs:
                for l in leafs:
                    locations.remove(l)
                    if l not in parent:
                        continue
                    for key in keys:
                        parent_key = (parent[l],) + key
                        quantities.setdefault(parent_key, 0)
                        quantities[parent_key] += quantities.get((l,) + key, 0)
                next_leafs = set(locations)
                for l in locations:
                    if l not in parent:
                        continue
                    if parent[l] in next_leafs and parent[l] in locations:
                        next_leafs.remove(parent[l])
                leafs = next_leafs

            # clean result
            for key in quantities.keys():
                location = key[0]
                if location not in location_ids:
                    del quantities[key]

        # Round quantities
        default_uom = dict((p.id, p.default_uom) for p in
            Product.browse(list(res_product_ids)))
        for key, quantity in quantities.iteritems():
            location = key[0]
            product = product_getter(key)
            uom = default_uom[product]
            quantities[key] = Uom.round(quantity, uom.rounding)

        return quantities
