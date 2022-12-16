# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import hashlib
import operator
from decimal import Decimal
from collections import OrderedDict, defaultdict
from itertools import groupby

from sql import Literal, Union, Column, Null, For
from sql.aggregate import Sum
from sql.conditionals import Coalesce, Case

from trytond.i18n import gettext
from trytond.model import Workflow, Model, ModelView, ModelSQL, fields, Check
from trytond.model.exceptions import AccessError
from trytond.pyson import Eval, If, Bool
from trytond.tools import reduce_ids
from trytond.transaction import Transaction
from trytond.pool import Pool

from trytond.modules.product import price_digits, round_price

from .exceptions import MoveOriginWarning

STATES = {
    'readonly': Eval('state').in_(['cancel', 'assigned', 'done']),
}
DEPENDS = ['state']
LOCATION_DOMAIN = [
    If(Eval('state').in_(['staging', 'draft', 'cancel']),
        ('type', 'not in', ['warehouse']),
        ('type', 'not in', ['warehouse', 'view'])),
    If(~Eval('state').in_(['done', 'cancel']),
        ('active', '=', True),
        ()),
    ]
LOCATION_DEPENDS = ['state']


class StockMixin(object):
    '''Mixin class with helper to setup stock quantity field.'''
    __slots__ = ()

    @classmethod
    def _quantity_context(cls, name):
        pool = Pool()
        Date = pool.get('ir.date')
        today = Date.today()
        context = Transaction().context
        new_context = {}
        stock_date_end = context.get('stock_date_end')
        if name == 'quantity':
            new_context['forecast'] = False
            if (stock_date_end or datetime.date.max) > today:
                new_context['stock_date_end'] = today
        elif name == 'forecast_quantity':
            new_context['forecast'] = True
            if not stock_date_end:
                new_context['stock_date_end'] = datetime.date.max
        return new_context

    @classmethod
    def _get_quantity(cls, records, name, location_ids,
            grouping=('product',), grouping_filter=None, position=-1):
        """
        Compute for each record the stock quantity in the default uom of the
        product.

        location_ids is the list of IDs of locations to take account to compute
            the stock.
        grouping defines how stock moves are grouped.
        grouping_filter is a tuple of values, for the Move's field at the same
            position in grouping tuple, used to filter which moves are used to
            compute quantities. If it is None all the products are used.
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

        with_childs = Transaction().context.get(
            'with_childs', len(location_ids) == 1)

        with Transaction().set_context(cls._quantity_context(name)):
            pbl = Product.products_by_location(
                location_ids,
                with_childs=with_childs,
                grouping=grouping,
                grouping_filter=grouping_filter)

        for key, quantity in pbl.items():
            # pbl could return None in some keys
            if (key[position] is not None
                    and key[position] in quantities):
                quantities[key[position]] += quantity
        return quantities

    @classmethod
    def _search_quantity(cls, name, location_ids, domain=None,
            grouping=('product',), position=-1):
        """
        Compute the domain to filter records which validates the domain over
        quantity field.

        location_ids is the list of IDs of locations to take account to compute
            the stock.
        grouping defines how stock moves are grouped.
        position defines which field of grouping corresponds to the record
            whose quantity is computed.
        """
        pool = Pool()
        Product = pool.get('product.product')

        if not location_ids or not domain:
            return []
        with_childs = Transaction().context.get(
            'with_childs', len(location_ids) == 1)

        with Transaction().set_context(cls._quantity_context(name)):
            pbl = Product.products_by_location(
                location_ids, with_childs=with_childs, grouping=grouping)

        _, operator_, operand = domain
        operator_ = {
            '=': operator.eq,
            '>=': operator.ge,
            '>': operator.gt,
            '<=': operator.le,
            '<': operator.lt,
            '!=': operator.ne,
            'in': lambda v, l: v in l,
            'not in': lambda v, l: v not in l,
            }.get(operator_, lambda v, l: False)
        record_ids = []
        for key, quantity in pbl.items():
            if operator_(quantity, operand):
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
        domain=[
            ('type', '!=', 'service'),
            If(Bool(Eval('product_uom_category')),
                ('default_uom_category', '=', Eval('product_uom_category')),
                ())
            ],
        depends=DEPENDS + ['product_uom_category'],
        help="The product that the move is associated with.")
    product_uom_category = fields.Function(
        fields.Many2One('product.uom.category', 'Product Uom Category'),
        'on_change_with_product_uom_category')
    uom = fields.Many2One("product.uom", "Uom", required=True,
        states={
            'readonly': (Eval('state').in_(['cancel', 'assigned', 'done'])
                | Eval('unit_price')),
            },
        domain=[
            ('category', '=', Eval('product_uom_category')),
            ],
        depends=['state', 'unit_price', 'product_uom_category'],
        help="The unit in which the quantity is specified.")
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
        'on_change_with_unit_digits')
    quantity = fields.Float("Quantity", required=True,
        digits=(16, Eval('unit_digits', 2)), states=STATES,
        depends=['state', 'unit_digits'],
        help="The amount of stock moved.")
    internal_quantity = fields.Float('Internal Quantity', readonly=True,
        required=True)
    from_location = fields.Many2One("stock.location", "From Location",
        select=True, required=True, states=STATES,
        depends=DEPENDS + LOCATION_DEPENDS, domain=LOCATION_DOMAIN,
        help="Where the stock is moved from.")
    to_location = fields.Many2One("stock.location", "To Location", select=True,
        required=True, states=STATES,
        depends=DEPENDS + LOCATION_DEPENDS, domain=LOCATION_DOMAIN,
        help="Where the stock is moved to.")
    shipment = fields.Reference('Shipment', selection='get_shipment',
        readonly=True, select=True,
        help="Used to group several stock moves together.")
    origin = fields.Reference('Origin', selection='get_origin', select=True,
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'],
        help="The source of the stock move.")
    planned_date = fields.Date("Planned Date", states={
            'readonly': (Eval('state').in_(['cancel', 'assigned', 'done'])
                | Eval('shipment'))
            }, depends=['state', 'shipment'],
        select=True,
        help="When the stock is expected to be moved.")
    effective_date = fields.Date("Effective Date", select=True,
        states={
            'required': Eval('state') == 'done',
            'readonly': (Eval('state').in_(['cancel', 'done'])
                | Eval('shipment')),
            },
        depends=['state', 'shipment'],
        help="When the stock was actually moved.")
    state = fields.Selection([
        ('staging', 'Staging'),
        ('draft', 'Draft'),
        ('assigned', 'Assigned'),
        ('done', 'Done'),
        ('cancel', 'Canceled'),
        ], 'State', select=True, readonly=True,
        help="The current state of the stock move.")
    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': Eval('state') != 'draft',
            },
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
        depends=['state'],
        help="The company the stock move is associated with.")
    unit_price = fields.Numeric('Unit Price', digits=price_digits,
        states={
            'invisible': ~Eval('unit_price_required'),
            'required': Bool(Eval('unit_price_required')),
            'readonly': Eval('state') != 'draft',
            },
        depends=['unit_price_required', 'state'])
    unit_price_updated = fields.Boolean(
        "Unit Price Updated", readonly=True,
        states={
            'invisible': Eval('state') != 'done',
            },
        depends=['state'])
    cost_price = fields.Numeric('Cost Price', digits=price_digits,
        readonly=True)
    currency = fields.Many2One('currency.currency', 'Currency',
        states={
            'invisible': ~Eval('unit_price_required'),
            'required': Bool(Eval('unit_price_required')),
            'readonly': Eval('state') != 'draft',
            },
        depends=['unit_price_required', 'state'],
        help="The currency in which the unit price is specified.")
    unit_price_required = fields.Function(
        fields.Boolean('Unit Price Required'),
        'on_change_with_unit_price_required')
    assignation_required = fields.Function(
        fields.Boolean('Assignation Required'),
        'on_change_with_assignation_required')

    @classmethod
    def __setup__(cls):
        super(Move, cls).__setup__()
        cls._deny_modify_assigned = set(['product', 'uom', 'quantity',
            'from_location', 'to_location', 'company', 'currency'])
        cls._deny_modify_done_cancel = (cls._deny_modify_assigned
            | set(['planned_date', 'effective_date', 'state']))
        cls._allow_modify_closed_period = {'cost_price'}

        t = cls.__table__()
        cls._sql_constraints += [
            ('check_move_qty_pos', Check(t, t.quantity >= 0),
                'stock.msg_move_quantity_positive'),
            ('check_move_internal_qty_pos',
                Check(t, t.internal_quantity >= 0),
                'stock.msg_move_internal_quantity_positive'),
            ('check_from_to_locations',
                Check(t, t.from_location != t.to_location),
                'stock.msg_move_from_to_location'),
            ]
        cls._order[0] = ('id', 'DESC')
        cls._transitions |= set((
                ('staging', 'draft'),
                ('staging', 'cancel'),
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
                    'readonly': Eval('shipment'),
                    'depends': ['state', 'shipment'],
                    },
                'draft': {
                    'invisible': ~Eval('state').in_(['assigned']),
                    'readonly': Eval('shipment'),
                    'depends': ['state', 'shipment'],
                    },
                'assign': {
                    'invisible': ~Eval('state').in_(['assigned']),
                    'depends': ['state'],
                    },
                'do': {
                    'invisible': ~Eval('state').in_(['draft', 'assigned']),
                    'readonly': (Eval('shipment')
                        | (Eval('assignation_required', True)
                            & (Eval('state') == 'draft'))),
                    'depends': ['state', 'assignation_required', 'shipment'],
                    },
                })

    @classmethod
    def __register__(cls, module_name):
        sql_table = cls.__table__()

        super(Move, cls).__register__(module_name)
        table = cls.__table_handler__(module_name)

        # Add index on create_date
        table.index_action('create_date', action='add')

        # Index for period join in compute_quantities_query
        table.index_action([
                Coalesce(sql_table.effective_date,
                    sql_table.planned_date,
                    datetime.date.max)], action='add')

    @staticmethod
    def default_planned_date():
        return Transaction().context.get('planned_date')

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @classmethod
    def default_unit_price_updated(cls):
        return True

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

    @fields.depends('uom')
    def on_change_with_unit_digits(self, name=None):
        if self.uom:
            return self.uom.digits
        return 2

    @fields.depends('product', 'uom')
    def on_change_product(self):
        if self.product:
            if (not self.uom
                    or self.uom.category != self.product.default_uom.category):
                self.uom = self.product.default_uom
                self.unit_digits = self.product.default_uom.digits

    @fields.depends('product')
    def on_change_with_product_uom_category(self, name=None):
        if self.product:
            return self.product.default_uom_category.id

    @fields.depends('from_location', 'to_location')
    def on_change_with_unit_price_required(self, name=None):
        from_type = self.from_location.type if self.from_location else None
        to_type = self.to_location.type if self.to_location else None

        if from_type == 'supplier' and to_type == 'storage':
            return True
        if from_type == 'production':
            return True
        if from_type == 'storage' and to_type == 'customer':
            return True
        if from_type == 'storage' and to_type == 'supplier':
            return True
        return False

    @fields.depends('from_location')
    def on_change_with_assignation_required(self, name=None):
        if self.from_location:
            return self.from_location.type in {'storage', 'view'}

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

    @classmethod
    def _get_origin(cls):
        'Return list of Model names for origin Reference'
        return [cls.__name__, 'stock.inventory.line']

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
        for company, moves in groupby(moves, lambda m: m.company):
            periods = Period.search([
                    ('state', '=', 'closed'),
                    ('company', '=', company.id),
                    ], order=[('date', 'DESC')], limit=1)
            if periods:
                period, = periods
                for move in moves:
                    date = (move.effective_date if move.effective_date
                        else move.planned_date)
                    if date and date <= period.date:
                        raise AccessError(
                            gettext('stock.msg_move_modify_period_close',
                                move=move.rec_name,
                                period=period.rec_name))

    def get_rec_name(self, name):
        pool = Pool()
        Lang = pool.get('ir.lang')
        lang = Lang.get()
        return (lang.format(
                '%.*f', (self.uom.digits, self.quantity))
            + '%s %s' % (self.uom.symbol, self.product.rec_name))

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('product.rec_name',) + tuple(clause[1:])]

    def _compute_product_cost_price(self, direction):
        """
        Update the cost price on the given product.
        The direction must be "in" if incoming and "out" if outgoing.
        """
        pool = Pool()
        Uom = pool.get('product.uom')
        Currency = pool.get('currency.currency')

        if direction == 'in':
            quantity = self.quantity
        elif direction == 'out':
            quantity = -self.quantity
        qty = Uom.compute_qty(self.uom, quantity, self.product.default_uom)

        qty = Decimal(str(qty))
        product_qty = Decimal(str(self.product.quantity))
        # convert wrt currency
        with Transaction().set_context(date=self.effective_date):
            unit_price = Currency.compute(self.currency, self.unit_price,
                self.company.currency, round=False)
        # convert wrt to the uom
        unit_price = Uom.compute_price(self.uom, unit_price,
            self.product.default_uom)
        cost_price = self.product.get_multivalue(
            'cost_price', **self._cost_price_pattern)
        if product_qty + qty > 0 and product_qty >= 0:
            new_cost_price = (
                (cost_price * product_qty) + (unit_price * qty)
                ) / (product_qty + qty)
        elif direction == 'in':
            new_cost_price = unit_price
        elif direction == 'out':
            new_cost_price = cost_price
        return round_price(new_cost_price)

    @staticmethod
    def _get_internal_quantity(quantity, uom, product):
        Uom = Pool().get('product.uom')
        internal_quantity = Uom.compute_qty(uom, quantity,
            product.default_uom, round=True)
        return internal_quantity

    def set_effective_date(self):
        pool = Pool()
        Date = pool.get('ir.date')

        if not self.effective_date and self.shipment:
            self.effective_date = self.shipment.effective_date
        if not self.effective_date:
            self.effective_date = Date.today()

    @classmethod
    def view_attributes(cls):
        return [
            ('/tree', 'visual', If(Eval('state') == 'cancel', 'muted', '')),
            ]

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, moves):
        cls.write(moves, {
                'effective_date': None,
                })

    @classmethod
    @ModelView.button
    @Workflow.transition('assigned')
    def assign(cls, moves):
        cls.check_origin(moves)

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def do(cls, moves):
        pool = Pool()
        Product = pool.get('product.product')

        def set_cost_values(cost_values):
            Value = Product.multivalue_model('cost_price')
            values = []
            for product, cost_price, pattern in cost_values:
                values.extend(product.set_multivalue(
                        'cost_price', cost_price, save=False, **pattern))
            Value.save(values)

        cls.check_origin(moves)
        for key, grouped_moves in groupby(moves, key=cls._cost_price_key):
            to_save = []
            cost_values = []
            products = set()
            grouped_moves = list(grouped_moves)
            context = dict(key)
            context.update(cls._cost_price_context(grouped_moves))
            with Transaction().set_context(context):
                grouped_moves = cls.browse(grouped_moves)
                for move in grouped_moves:
                    if move.product in products:
                        # The average computation of product cost price
                        # requires each previous move of the same product to be
                        # saved
                        cls.save(to_save)
                        set_cost_values(cost_values)
                        del to_save[:]
                        del cost_values[:]
                        products.clear()

                    move.set_effective_date()
                    cost_price = move._do()
                    if cost_price is not None:
                        cost_values.append(
                            (move.product, cost_price,
                                move._cost_price_pattern))
                    if move.cost_price is None:
                        if cost_price is None:
                            cost_price = move.product.get_multivalue(
                                'cost_price', **move._cost_price_pattern)
                        move.cost_price = cost_price
                    move.state = 'done'

                    to_save.append(move)
                    products.add(move.product)

                if to_save:
                    cls.save(to_save)
                if cost_values:
                    set_cost_values(cost_values)

    @property
    def _cost_price_pattern(self):
        return {
            'company': self.company.id,
            }

    def _cost_price_key(self):
        return (
            ('company', self.company.id),
            )

    @classmethod
    def _cost_price_context(cls, moves):
        pool = Pool()
        Location = pool.get('stock.location')
        Date = pool.get('ir.date')
        context = {}
        locations = Location.search([
                ('type', '=', 'storage'),
                ])
        context['with_childs'] = False
        context['locations'] = [l.id for l in locations]
        context['stock_date_end'] = Date.today()
        context['company'] = moves[0].company.id
        return context

    def _do(self):
        if (self.from_location.type in ('supplier', 'production')
                and self.to_location.type == 'storage'
                and self.product.cost_price_method == 'average'):
            return self._compute_product_cost_price('in')
        elif (self.to_location.type == 'supplier'
                and self.from_location.type == 'storage'
                and self.product.cost_price_method == 'average'):
            return self._compute_product_cost_price('out')

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, moves):
        pass

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Product = pool.get('product.product')
        Uom = pool.get('product.uom')

        vlist = [x.copy() for x in vlist]
        # Use ordered dict to optimize cache alignment
        products, uoms = OrderedDict(), OrderedDict()
        for vals in vlist:
            products[vals['product']] = None
            uoms[vals['uom']] = None
        id2product = {p.id: p for p in Product.browse(products.keys())}
        id2uom = {u.id: u for u in Uom.browse(uoms.keys())}
        for vals in vlist:
            assert vals.get('state', cls.default_state()
                ) in ['draft', 'staging']
            product = id2product[int(vals['product'])]
            uom = id2uom[int(vals['uom'])]
            internal_quantity = cls._get_internal_quantity(
                vals['quantity'], uom, product)
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
                        raise AccessError(
                            gettext('stock.msg_move_modify_assigned',
                                move=move.rec_name))
            if cls._deny_modify_done_cancel & vals_set:
                for move in moves:
                    if move.state in ('done', 'cancel'):
                        raise AccessError(
                            gettext('stock.msg_move_modify_%s' % move.state,
                                move=move.rec_name))

        super(Move, cls).write(*args)

        to_write = []
        unit_price_update = []
        actions = iter(args)
        for moves, values in zip(actions, actions):
            if any(f not in cls._allow_modify_closed_period for f in values):
                cls.check_period_closed(moves)
            for move in moves:
                internal_quantity = cls._get_internal_quantity(move.quantity,
                        move.uom, move.product)
                if (internal_quantity != move.internal_quantity
                        and internal_quantity
                        != values.get('internal_quantity')):
                    to_write.extend(([move], {
                            'internal_quantity': internal_quantity,
                            }))
                if move.state == 'done' and 'unit_price' in values:
                    unit_price_update.append(move)

        if to_write:
            cls.write(*to_write)
        if unit_price_update:
            cls.write(unit_price_update, {'unit_price_updated': True})

    @classmethod
    def delete(cls, moves):
        for move in moves:
            if move.state not in {'staging', 'draft', 'cancel'}:
                raise AccessError(
                    gettext('stock.msg_move_delete_draft_cancel',
                        move=move.rec_name))
        super(Move, cls).delete(moves)

    @staticmethod
    def check_origin_types():
        "Location types to check for origin"
        return set()

    @classmethod
    def check_origin(cls, moves, types=None):
        pool = Pool()
        Warning = pool.get('res.user.warning')
        if types is None:
            types = cls.check_origin_types()
        if not types:
            return

        def no_origin(move):
            return ((move.from_location.type in types)
                ^ (move.to_location.type in types)
                and not move.origin)
        moves = list(filter(no_origin, moves))
        if moves:
            names = ', '.join(m.rec_name for m in moves[:5])
            if len(moves) > 5:
                names += '...'
            warning_name = '%s.done' % hashlib.md5(
                str(moves).encode('utf-8')).hexdigest()
            if Warning.check(warning_name):
                raise MoveOriginWarning(warning_name,
                    gettext('stock.msg_move_no_origin',
                        moves=names))

    def pick_product(self, location_quantities):
        """
        Pick the product across the location. Naive (fast) implementation.
        Return a list of tuple (location, quantity) for quantities that can be
        picked.
        """
        to_pick = []
        needed_qty = self.quantity
        for location, available_qty in location_quantities.items():
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
        if self.product.consumable and self.from_location.type != 'view':
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
        Period = pool.get('stock.period')
        transaction = Transaction()
        database = transaction.database
        connection = transaction.connection

        if not moves:
            return True

        if with_childs:
            locations = Location.search([
                    ('parent', 'child_of',
                        [x.from_location.id for x in moves]),
                    ])
        else:
            locations = list(set((m.from_location for m in moves)))
        location_ids = [l.id for l in locations]
        product_ids = list(set((m.product.id for m in moves)))
        companies = {m.company for m in moves}
        stock_date_end = Date.today()

        if database.has_select_for():
            for company in companies:
                table = cls.__table__()
                query = table.select(Literal(1),
                    where=(table.to_location.in_(location_ids)
                        | table.from_location.in_(location_ids))
                    & table.product.in_(product_ids)
                    & (table.company == company.id),
                    for_=For('UPDATE', nowait=True))

                PeriodCache = Period.get_cache(grouping)
                if PeriodCache:
                    periods = Period.search([
                            ('date', '<', stock_date_end),
                            ('company', '=', company.id),
                            ('state', '=', 'closed'),
                            ], order=[('date', 'DESC')], limit=1)
                    if periods:
                        period, = periods
                        query.where &= Coalesce(
                            table.effective_date,
                            table.planned_date,
                            datetime.date.max) > period.date

                with connection.cursor() as cursor:
                    cursor.execute(*query)
        else:
            database.lock(connection, cls._table)

        pblc = {}
        for company in companies:
            with Transaction().set_context(
                    stock_date_end=stock_date_end,
                    stock_assign=True,
                    company=company.id):
                pblc[company.id] = Product.products_by_location(
                    location_ids,
                    grouping=grouping,
                    grouping_filter=(product_ids,))

        def get_key(move, location):
            key = (location.id,)
            for field in grouping:
                value = getattr(move, field)
                if isinstance(value, Model):
                    value = value.id
                key += (value,)
            return key

        child_locations = {}
        to_write = []
        to_assign = []
        success = True
        for move in moves:
            if move.state != 'draft':
                if move.state == 'staging':
                    success = False
                continue
            pbl = pblc[move.company.id]
            # Keep location order for pick_product
            location_qties = OrderedDict()
            if with_childs:
                childs = child_locations.get(move.from_location)
                if childs is None:
                    childs = Location.search([
                            ('parent', 'child_of', [move.from_location.id]),
                            ('type', '!=', 'view'),
                            ])
                    child_locations[move.from_location] = childs
            else:
                childs = [move.from_location]
            for location in childs:
                key = get_key(move, location)
                if key in pbl:
                    location_qties[location] = Uom.compute_qty(
                        move.product.default_uom, pbl[key], move.uom,
                        round=False)
            # Prevent to pick from the destination location
            location_qties.pop(move.to_location, None)
            try:
                # Try first to pick from source location
                location_qties.move_to_end(move.from_location, last=False)
            except KeyError:
                pass

            to_pick = move.pick_product(location_qties)

            picked_qties = 0.0
            for _, qty in to_pick:
                picked_qties += qty

            if move.quantity - picked_qties >= move.uom.rounding:
                success = False
                first = False
                values = {
                    'quantity': move.uom.round(
                        move.quantity - picked_qties),
                    }
                to_write.extend([[move], values])
            else:
                first = True
            for from_location, qty in to_pick:
                values = {
                    'from_location': from_location.id,
                    'quantity': move.uom.round(qty),
                    }
                if first:
                    to_write.extend([[move], values])
                    to_assign.append(move)
                    first = False
                else:
                    with Transaction().set_context(_stock_move_split=True):
                        to_assign.extend(cls.copy([move], default=values))

                qty_default_uom = Uom.compute_qty(move.uom, qty,
                        move.product.default_uom, round=False)

                from_key = get_key(move, from_location)
                pbl[from_key] = pbl.get(from_key, 0.0) - qty_default_uom
        if to_write:
            cls.write(*to_write)
        if to_assign:
            cls.assign(to_assign)
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
            stock_assign: if set compute also the assigned outgoing moves as
                done at the stock_date_end except for delta which is at the
                planned date.
            forecast: if set compute the forecast quantity.
            stock_destinations: A list of location ids. If set, restrict the
                computation to moves from and to those locations.
        If with_childs, it computes also for child locations.
        grouping is a tuple of Move (or Product if prefixed by 'product.')
            field names and defines how stock moves are grouped.
        grouping_filter is a tuple of values, for the Move's field at the same
            position in grouping tuple, used to filter which moves are used to
            compute quantities. It must be None or have the same number of
            elements than grouping. If no grouping_filter is provided it
            returns quantities for all products.

        The query return the location as first column, after the fields in
            grouping, and the last column is the quantity.
        """
        pool = Pool()
        User = pool.get('res.user')
        Location = pool.get('stock.location')
        Date = pool.get('ir.date')
        Period = pool.get('stock.period')
        Move = pool.get('stock.move')
        Product = pool.get('product.product')

        move = Move.__table__()
        today = Date.today()

        if not location_ids:
            return None
        context = Transaction().context.copy()

        use_product = False
        for field in grouping:
            if field.startswith('product.'):
                Model = Product
                field = field[len('product.'):]
                use_product = True
            else:
                Model = Move
            if field not in Model._fields:
                raise ValueError('"%s" has no field "%s"' % (Model, field))
        assert grouping_filter is None or len(grouping_filter) <= len(grouping)
        assert len(set(grouping)) == len(grouping)

        company = User(Transaction().user).company

        def get_column(name, table, product):
            if name.startswith('product.'):
                column = Column(product, name[len('product.'):])
            else:
                column = Column(table, name)
            return column.as_(name)

        if use_product:
            product = Product.__table__()
            columns = ['id', 'state', 'effective_date', 'planned_date',
            'internal_quantity', 'from_location', 'to_location', 'company']
            columns += [c for c in grouping if c not in columns]
            columns = [get_column(c, move, product) for c in columns]
            move = (move
                .join(product, condition=move.product == product.id)
                .select(*columns))

        PeriodCache = Period.get_cache(grouping)
        period = None
        if PeriodCache:
            period_cache = PeriodCache.__table__()
            period_table = Period.__table__()
            if use_product:
                product_cache = Product.__table__()
                columns = ['internal_quantity', 'period', 'location']
                columns += [c for c in grouping if c not in columns]
                columns = [get_column(c, period_cache, product_cache)
                    for c in columns]
                period_cache = (period_cache
                    .join(product_cache,
                        condition=(period_cache.product == product_cache.id))
                    .join(period_table,
                        condition=(period_cache.period == period_table.id)
                        & ((period_table.company == company.id)
                            if company else Literal(True)))
                    .select(*columns))

        if with_childs:
            # Replace tables with union which replaces flat children locations
            # by their parent location.
            from_location = Location.__table__()
            from_parent_location = Location.__table__()
            to_location = Location.__table__()
            to_parent_location = Location.__table__()
            columns = ['id', 'state', 'effective_date', 'planned_date',
                'internal_quantity', 'company']
            columns += [c for c in grouping if c not in columns]
            columns = [Column(move, c).as_(c) for c in columns]

            move_with_parent = (move
                .join(from_location,
                    condition=move.from_location == from_location.id)
                .join(from_parent_location, type_='LEFT',
                    condition=from_location.parent == from_parent_location.id)
                .join(to_location,
                    condition=move.to_location == to_location.id)
                .join(to_parent_location, type_='LEFT',
                    condition=to_location.parent == to_parent_location.id))

            move = Union(
                # Moves not linked to any flat location
                move_with_parent.select(
                    move.from_location.as_('from_location'),
                    move.to_location.as_('to_location'),
                    *columns,
                    where=(Coalesce(from_parent_location.flat_childs, False)
                        != Literal(True))
                    & (Coalesce(to_parent_location.flat_childs, False)
                        != Literal(True))),
                # Append moves linked from/to flat locations to their parents
                move_with_parent.select(
                    Case(
                        (from_parent_location.flat_childs,
                            from_parent_location.id),
                        else_=move.from_location).as_('from_location'),
                    Case(
                        (to_parent_location.flat_childs,
                            to_parent_location.id),
                        else_=move.to_location).as_('to_location'),
                    *columns,
                    where=(from_parent_location.flat_childs == Literal(True))
                    | (to_parent_location.flat_childs == Literal(True))),
                # Append moves linked to from/to flat locations only
                move_with_parent.select(
                    Case(
                        (from_parent_location.flat_childs,
                            from_location.id),
                        else_=Null).as_('from_location'),
                    Case(
                        (to_parent_location.flat_childs,
                            to_location.id),
                        else_=Null).as_('to_location'),
                    *columns,
                    where=(from_parent_location.flat_childs == Literal(True))
                    | (to_parent_location.flat_childs == Literal(True))),
                all_=True)

            if PeriodCache:
                location = Location.__table__()
                parent_location = Location.__table__()
                columns = ['internal_quantity', 'period'] + list(grouping)
                columns = [Column(period_cache, c).as_(c) for c in columns]
                period_cache = Union(
                    period_cache.select(
                        period_cache.location.as_('location'),
                        *columns),
                    period_cache.join(location,
                        condition=period_cache.location == location.id
                        ).join(parent_location, type_='LEFT',
                        condition=location.parent == parent_location.id
                        ).select(
                        parent_location.id.as_('location'),
                        *columns,
                        where=parent_location.flat_childs == Literal(True)),
                    all_=True)

        if not context.get('stock_date_end'):
            context['stock_date_end'] = datetime.date.max

        # date end in the past or today: filter on state done
        if (context['stock_date_end'] < today
                or (context['stock_date_end'] == today
                    and not context.get('forecast'))):

            def state_date_clause(stock_assign):
                return (move.state.in_(['done',
                        'assigned' if stock_assign else 'done'])
                    & (
                        (
                            (move.effective_date == Null)
                            & (move.planned_date <= context['stock_date_end'])
                            )
                        | (move.effective_date <= context['stock_date_end'])
                        | (move.state == (
                                'assigned'
                                if not context.get('stock_date_start')
                                else ''))
                        ))
            state_date_clause_in = state_date_clause(False)
            state_date_clause_out = state_date_clause(
                context.get('stock_assign'))
        # future date end: filter move on state done and date
        # before today, or on all state and date between today and
        # date_end.
        else:
            def state_date_clause(stock_assign):
                return ((move.state.in_(['done',
                                'assigned' if stock_assign else 'done'])
                        & (
                            (
                                (move.effective_date == Null)
                                & (move.planned_date <= today)
                                )
                            | (move.effective_date <= today)
                            | (move.state == (
                                    'assigned'
                                    if not context.get('stock_date_start')
                                    else ''))
                            )
                        )
                    | (move.state.in_(['done', 'assigned', 'draft'])
                        & (
                            (
                                (move.effective_date == Null)
                                & (Coalesce(
                                        move.planned_date, datetime.date.max)
                                    <= context['stock_date_end'])
                                & (Coalesce(
                                        move.planned_date, datetime.date.max)
                                    >= today)
                                )
                            | (
                                (move.effective_date
                                    <= context['stock_date_end'])
                                & (move.effective_date >= today)
                                )
                            | (move.state == (
                                    'assigned'
                                    if not context.get('stock_date_start')
                                    else ''))
                            )
                        )
                    )
            state_date_clause_in = state_date_clause(False)
            state_date_clause_out = state_date_clause(
                context.get('stock_assign'))

        if context.get('stock_date_start'):
            if context['stock_date_start'] > today:
                def state_date_clause():
                    return (move.state.in_(['done', 'assigned', 'draft'])
                        & (
                            (
                                (move.effective_date == Null)
                                & (
                                    (move.planned_date
                                        >= context['stock_date_start'])
                                    | (move.planned_date == Null)
                                    )
                                )
                            | (move.effective_date
                                >= context['stock_date_start'])
                            )
                        )
                state_date_clause_in &= state_date_clause()
                state_date_clause_out &= state_date_clause()
            else:
                def state_date_clause(stock_assign):
                    return ((
                            move.state.in_(['done', 'assigned', 'draft'])
                            & (
                                (
                                    (move.effective_date == Null)
                                    & (
                                        (move.planned_date >= today)
                                        | (move.planned_date == Null)
                                        )
                                    )
                                | (move.effective_date >= today)
                                )
                            )
                        | (
                            move.state.in_(['done',
                                    'assigned' if stock_assign else 'done'])
                            & (
                                (
                                    (move.effective_date == Null)
                                    & (
                                        (
                                            (move.planned_date
                                                >= context['stock_date_start'])
                                            & (move.planned_date < today)
                                            )
                                        | (move.planned_date == Null)
                                        )
                                    )
                                | (
                                    (move.effective_date
                                        >= context['stock_date_start'])
                                    & (move.effective_date < today)
                                    )
                                )
                            )
                        )
                state_date_clause_in &= state_date_clause(False)
                state_date_clause_out &= state_date_clause(
                    context.get('stock_assign'))
        elif PeriodCache:
            periods = Period.search([
                    ('date', '<=', context['stock_date_end']),
                    ('state', '=', 'closed'),
                    ('company', '=', company.id if company else -1),
                    ], order=[('date', 'DESC')], limit=1)
            if periods:
                period, = periods

                def state_date_clause():
                    return (Coalesce(move.effective_date, move.planned_date,
                        datetime.date.max) > period.date)
                state_date_clause_in &= state_date_clause()
                state_date_clause_out &= state_date_clause()

        if with_childs:
            location_query = _location_children(location_ids, query=True)
        else:
            location_query = location_ids[:]

        if PeriodCache:
            from_period = period_cache
        where = where_period = Literal(True)
        if grouping_filter and any(grouping_filter):
            for fieldname, grouping_ids in zip(grouping, grouping_filter):
                if not grouping_ids:
                    continue
                column = Column(move, fieldname)
                if PeriodCache:
                    cache_column = Column(period_cache, fieldname)
                if isinstance(grouping_ids[0], (int, float, Decimal)):
                    where &= reduce_ids(column, grouping_ids)
                    if PeriodCache:
                        where_period &= reduce_ids(cache_column, grouping_ids)
                else:
                    where &= column.in_(grouping_ids)
                    if PeriodCache:
                        where_period &= cache_column.in_(grouping_ids)

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
        move_keys_alias = [Column(move, key).as_(key) for key in grouping]
        move_keys = [Column(move, key) for key in grouping]
        query = move.select(move.to_location.as_('location'),
            Sum(move.internal_quantity).as_('quantity'),
            *move_keys_alias,
            where=state_date_clause_in
            & where
            & move.to_location.in_(location_query)
            & ((move.company == company.id) if company else Literal(True))
            & dest_clause_from,
            group_by=[move.to_location] + move_keys)
        query = Union(query, move.select(move.from_location.as_('location'),
                (-Sum(move.internal_quantity)).as_('quantity'),
                *move_keys_alias,
                where=state_date_clause_out
                & where
                & move.from_location.in_(location_query)
                & ((move.company == company.id) if company else Literal(True))
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
        Product = pool.get('product.product')
        Template = pool.get('product.template')

        assert query is not None, (
            "Query in Move.compute_quantities() can't be None")
        assert 'product' in grouping or 'product.template' in grouping

        cursor = Transaction().connection.cursor()
        cursor.execute(*query)
        raw_lines = cursor.fetchall()

        if 'product' in grouping:
            id_name = 'product'
            Model = Product
        else:
            id_name = 'product.template'
            Model = Template
        id_getter = operator.itemgetter(grouping.index(id_name) + 1)
        ids = set()
        quantities = defaultdict(int)
        keys = set()
        # We can do a quick loop without propagation if the request is for a
        # single location because all the locations are children and we can sum
        # them directly.
        if len(location_ids) == 1:
            location, = location_ids
        for line in raw_lines:
            if len(location_ids) > 1:
                location = line[0]
            key = tuple(line[1:-1])
            quantity = line[-1]
            quantities[(location,) + key] += quantity
            ids.add(id_getter(line))
            keys.add(key)

        # Propagate quantities on from child locations to their parents
        if with_childs and len(location_ids) > 1:
            # Fetch all child locations
            locations = _location_children(location_ids)
            # Generate a set of locations without childs and a dict
            # giving the parent of each location.
            leafs = set([l.id for l in locations])
            parent = {}
            for location in locations:
                if not location.parent or location.parent.flat_childs:
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
            for key in list(quantities.keys()):
                location = key[0]
                if location not in location_ids:
                    del quantities[key]

        # Round quantities
        default_uom = dict((p.id, p.default_uom) for p in
            Model.browse(list(ids)))
        for key, quantity in quantities.items():
            location = key[0]
            uom = default_uom[id_getter(key)]
            quantities[key] = uom.round(quantity)

        return quantities


def _location_children(location_ids, query=False):
    "Return children location without including flat children"
    pool = Pool()
    Location = pool.get('stock.location')
    nested_location_ids = []
    flat_location_ids = []
    for location in Location.browse(location_ids):
        if location.flat_childs:
            flat_location_ids.append(location.id)
        else:
            nested_location_ids.append(location.id)
    if nested_location_ids:
        return Location.search(['OR',
                [
                    ('parent', 'child_of', nested_location_ids),
                    ('parent.flat_childs', '!=', True),
                    ],
                ('id', 'in', location_ids),
                ], query=query, order=[])
    else:
        if query:
            return flat_location_ids
        else:
            return Location.browse(flat_location_ids)
