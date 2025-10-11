# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import copy
import datetime
import operator
from collections import defaultdict
from decimal import Decimal
from itertools import groupby

from sql import Column, For, Literal, Null, Union
from sql.aggregate import Max, Sum
from sql.conditionals import Case, Coalesce
from sql.functions import Round

from trytond.i18n import gettext
from trytond.model import (
    Check, Index, Model, ModelSQL, ModelView, Workflow, fields)
from trytond.model.exceptions import AccessError
from trytond.modules.product import price_digits, round_price
from trytond.pool import Pool
from trytond.pyson import Bool, Eval, If, TimeDelta
from trytond.tools import cached_property, grouped_slice, reduce_ids
from trytond.transaction import Transaction, without_check_access

from .exceptions import MoveFutureWarning, MoveOriginWarning

STATES = {
    'readonly': Eval('state').in_(['cancelled', 'assigned', 'done']),
}
LOCATION_DOMAIN = [
    If(Eval('state').in_(['staging', 'draft', 'cancelled'])
        | ((Eval('state') == 'assigned') & ~Eval('quantity')),
        ('type', 'not in', ['warehouse']),
        ('type', 'not in', ['warehouse', 'view'])),
    If(~Eval('state').in_(['done', 'cancelled']),
        ('active', '=', True),
        ()),
    ]


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
        Move = pool.get('stock.move')
        Uom = pool.get('product.uom')
        uom = Uom.__table__()

        if not location_ids or not domain:
            return []
        with_childs = Transaction().context.get(
            'with_childs', len(location_ids) == 1)
        _, operator_, operand = domain

        with Transaction().set_context(cls._quantity_context(name)):
            if (len(location_ids) == 1
                    and not Transaction().context.get('stock_skip_warehouse')):
                # We can use the compute quantities query if the request is for
                # a single location because all the locations are children and
                # so we can do a SUM.
                Operator = fields.SQL_OPERATORS[operator_]
                query = Move.compute_quantities_query(
                    location_ids, with_childs, grouping=grouping)
                col_id = Column(query, grouping[position])
                # We need to round the result to have same result as
                # products_by_location but as we do not have the unit, we use
                # the biggest digits of all unit as best approximation.
                quantity = Round(
                    fields.Numeric('quantity').sql_cast(Sum(query.quantity)),
                    uom.select(Max(uom.digits)))
                group_by = [Column(query, key).as_(key) for key in grouping]
                return [('id', 'in', query.select(
                            col_id,
                            group_by=group_by,
                            having=Operator(quantity, operand)))]

            pbl = Product.products_by_location(
                location_ids, with_childs=with_childs, grouping=grouping)

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
            if (quantity is not None and operand is not None
                    and operator_(quantity, operand)):
                # pbl could return None in some keys
                if key[position] is not None:
                    record_ids.append(key[position])

        return [('id', 'in', record_ids)]


class Move(Workflow, ModelSQL, ModelView):
    __name__ = 'stock.move'
    _order_name = 'product'
    product = fields.Many2One(
        'product.product', "Product", required=True, states=STATES,
        context={
            'company': Eval('company', -1),
            },
        search_context={
            'locations': If(Eval('from_location'),
                [Eval('from_location', -1)], []),
            'stock_date_end': (
                If(Eval('effective_date'),
                    Eval('effective_date', None),
                    Eval('planned_date', None))),
            },
        depends={'company'},
        help="The product that the move is associated with.")
    product_uom_category = fields.Function(
        fields.Many2One(
            'product.uom.category', "Product UoM Category",
            help="The category of Unit of Measure for the product."),
        'on_change_with_product_uom_category')
    unit = fields.Many2One(
        'product.uom', "Unit", required=True,
        states={
            'readonly': (Eval('state').in_(['cancelled', 'assigned', 'done'])
                | Eval('unit_price')),
            },
        domain=[
            If(~Eval('state').in_(['done', 'cancelled']),
                ('category', '=', Eval('product_uom_category', -1)),
                ()),
            ],
        help="The unit in which the quantity is specified.")
    quantity = fields.Float(
        "Quantity", digits='unit', required=True,
        states=STATES,
        domain=[
            ('quantity', '>=', 0),
            ],
        help="The amount of stock moved.")
    internal_quantity = fields.Float(
        "Internal Quantity", readonly=True, required=True,
        domain=[
            ('internal_quantity', '>=', 0),
            ])
    from_location = fields.Many2One(
        'stock.location', "From Location",
        required=True, states=STATES,
        domain=[
            LOCATION_DOMAIN,
            ('id', '!=', Eval('to_location', -1)),
            ],
        search_context={
            'company': Eval('company', -1),
            'product': Eval('product', -1),
            'stock_date_end': (
                If(Eval('effective_date'),
                    Eval('effective_date', None),
                    Eval('planned_date', None))),
            },
        help="Where the stock is moved from.")
    from_location_name = fields.Function(fields.Char(
            "From Location"),
        'on_change_with_from_location_name')
    to_location = fields.Many2One(
        'stock.location', "To Location",
        required=True, states=STATES,
        domain=[
            LOCATION_DOMAIN,
            ('id', '!=', Eval('from_location', -1)),
            ],
        search_context={
            'company': Eval('company', -1),
            'product': Eval('product', -1),
            'stock_date_end': (
                If(Eval('effective_date'),
                    Eval('effective_date', None),
                    Eval('planned_date', None))),
            },
        help="Where the stock is moved to.")
    to_location_name = fields.Function(fields.Char(
            "To Location"),
        'on_change_with_to_location_name')
    shipment = fields.Reference(
        "Shipment", selection='get_shipment', readonly=True,
        states={
            'invisible': ~Eval('shipment'),
            },
        help="Used to group several stock moves together.")
    origin = fields.Reference(
        "Origin", selection='get_origin',
        states={
            'readonly': Eval('state') != 'draft',
            },
        help="The source of the stock move.")
    outcome_moves = fields.One2Many(
        'stock.move', 'origin', "Outcome Moves", readonly=True)
    origin_planned_date = fields.Date(
        "Origin Planned Date", readonly=True,
        help="When the stock was expected to be moved originally.")
    planned_date = fields.Date(
        "Planned Date",
        states={
            'readonly': (
                Eval('state').in_(['cancelled', 'assigned', 'done'])
                | Eval('shipment')
                | Eval('_parent_shipment'))
            },
        help="When the stock is expected to be moved.")
    effective_date = fields.Date(
        "Effective Date",
        states={
            'required': Eval('state') == 'done',
            'readonly': (
                Eval('state').in_(['cancelled', 'done'])
                | Eval('shipment')
                | Eval('_parent_shipment')),
            },
        help="When the stock was actually moved.")
    delay = fields.Function(
        fields.TimeDelta(
            "Delay",
            states={
                'invisible': (
                    ~Eval('origin_planned_date')
                    & ~Eval('planned_date')),
                }),
        'get_delay')
    state = fields.Selection([
        ('staging', 'Staging'),
        ('draft', 'Draft'),
        ('assigned', 'Assigned'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
        ], "State", readonly=True, sort=False,
        help="The current state of the stock move.")
    company = fields.Many2One(
        'company.company', "Company", required=True,
        states={
            'readonly': Eval('state') != 'draft',
            },
        help="The company the stock move is associated with.")
    unit_price = fields.Numeric('Unit Price', digits=price_digits,
        domain=[
            If(~Eval('unit_price_required'),
                ('unit_price', '=', None),
                ()),
            ],
        states={
            'invisible': ~Eval('unit_price_required'),
            'required': Bool(Eval('unit_price_required')),
            'readonly': Eval('state') != 'draft',
            })
    unit_price_company = fields.Function(
        fields.Numeric("Unit Price", digits=price_digits,
            states={
                'invisible': ~Eval('unit_price_required'),
                },
            help="Unit price in company currency."),
        'get_unit_price_company')
    unit_price_updated = fields.Boolean(
        "Unit Price Updated", readonly=True,
        states={
            'invisible': Eval('state') != 'done',
            })
    cost_price = fields.Numeric(
        "Cost Price", digits=price_digits, readonly=True,
        domain=[
            If(~Eval('cost_price_required'),
                ('cost_price', '=', None),
                ()),
            ],
        states={
            'invisible': ~Eval('cost_price_required'),
            'required': (
                (Eval('state') == 'done')
                & Eval('cost_price_required', False)),
            })
    product_cost_price = fields.Numeric(
        "Product Cost Price", digits=price_digits, readonly=True,
        domain=[
            If(~Eval('cost_price_required'),
                ('product_cost_price', '=', None),
                ()),
            ],
        states={
            'invisible': ~Eval('cost_price_required'),
            },
        help="The cost price of the product "
        "when different from the cost price of the move.")
    currency = fields.Many2One('currency.currency', 'Currency',
        domain=[
            If(~Eval('unit_price_required'),
                ('id', '=', None),
                ()),
            ],
        states={
            'invisible': ~Eval('unit_price_required'),
            'required': Bool(Eval('unit_price_required')),
            'readonly': Eval('state') != 'draft',
            },
        help="The currency in which the unit price is specified.")
    unit_price_required = fields.Function(
        fields.Boolean('Unit Price Required'),
        'on_change_with_unit_price_required')
    cost_price_required = fields.Function(
        fields.Boolean("Cost Price Required"),
        'on_change_with_cost_price_required')
    assignation_required = fields.Function(
        fields.Boolean('Assignation Required'),
        'on_change_with_assignation_required',
        searcher='search_assignation_required')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.product.domain = [
            If(Bool(Eval('product_uom_category'))
                & ~Eval('state').in_(['done', 'cancelled']),
                ('default_uom_category', '=', Eval('product_uom_category')),
                ()),
            ('type', 'in', cls.get_product_types()),
            ]
        cls._deny_modify_assigned = set(['product', 'uom', 'quantity',
            'from_location', 'to_location', 'company'])
        cls._deny_modify_done_cancel = (cls._deny_modify_assigned
            | set(['planned_date', 'effective_date']))
        cls._allow_modify_closed_period = {
            'cost_price', 'unit_price', 'unit_price_updated', 'currency'}

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
        cls._sql_indexes.update({
                Index(
                    t,
                    (t.company, Index.Equality()),
                    (t.from_location, Index.Range()),
                    (Coalesce(
                            t.effective_date,
                            t.planned_date,
                            datetime.date.max),
                        Index.Range()),
                    (t.product, Index.Range())),
                Index(
                    t,
                    (t.company, Index.Equality()),
                    (t.to_location, Index.Range()),
                    (Coalesce(
                            t.effective_date,
                            t.planned_date,
                            datetime.date.max),
                        Index.Range()),
                    (t.product, Index.Range())),
                Index(
                    t,
                    (t.company, Index.Equality()),
                    (t.state, Index.Equality(cardinality='low')),
                    where=t.state.in_(['staging', 'draft', 'assigned'])),
                Index(
                    t,
                    (t.company, Index.Equality()),
                    (Coalesce(t.effective_date, t.planned_date),
                        Index.Range()),
                    (t.state, Index.Equality(cardinality='low')),
                    (t.product, Index.Range()),
                    where=t.state.in_(['done', 'assigned', 'draft'])),
                })
        cls._order[0] = ('id', 'DESC')
        cls._transitions |= set((
                ('staging', 'draft'),
                ('staging', 'cancelled'),
                ('draft', 'assigned'),
                ('draft', 'done'),
                ('draft', 'cancelled'),
                ('assigned', 'draft'),
                ('assigned', 'done'),
                ('assigned', 'cancelled'),
                ('done', 'cancelled'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': ~Eval('state').in_(['draft', 'assigned']),
                    'readonly': Eval('shipment') | Eval('_parent_shipment'),
                    'depends': ['state', 'shipment'],
                    },
                'draft': {
                    'invisible': ~Eval('state').in_(['assigned']),
                    'readonly': Eval('shipment') | Eval('_parent_shipment'),
                    'depends': ['state', 'shipment'],
                    },
                'do': {
                    'invisible': ~Eval('state').in_(['draft', 'assigned']),
                    'readonly': (
                        Eval('shipment') | Eval('_parent_shipment')
                        | (Eval('assignation_required', True)
                            & (Eval('state') == 'draft'))),
                    'depends': ['state', 'assignation_required', 'shipment'],
                    },
                })

    @classmethod
    def __register__(cls, module_name):
        table_h = cls.__table_handler__(module_name)

        # Migration from 6.8: rename uom to unit
        if (table_h.column_exist('uom')
                and not table_h.column_exist('unit')):
            table_h.column_rename('uom', 'unit')

        super().__register__(module_name)

    @classmethod
    def get_product_types(cls):
        return ['goods', 'assets']

    @staticmethod
    def default_planned_date():
        return Transaction().context.get('planned_date')

    def get_delay(self, name):
        pool = Pool()
        Date = pool.get('ir.date')
        planned_date = self.origin_planned_date or self.planned_date
        if planned_date is not None:
            if self.effective_date:
                return self.effective_date - planned_date
            elif self.planned_date:
                return self.planned_date - planned_date
            else:
                with Transaction().set_context(company=self.company.id):
                    today = Date.today()
                return today - planned_date

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @classmethod
    def default_unit_price_updated(cls):
        return True

    @fields.depends('product', 'unit')
    def on_change_product(self):
        if self.product:
            default_uom = self.product.default_uom
            if (not self.unit
                    or self.unit.category != default_uom.category):
                self.unit = default_uom

    @cached_property
    def product_name(self):
        return self.product.rec_name if self.product else ''

    @fields.depends('product')
    def on_change_with_product_uom_category(self, name=None):
        return self.product.default_uom_category if self.product else None

    @classmethod
    def default_internal_quantity(cls):
        # default value before compute of the field
        return 0

    @fields.depends('quantity', 'unit', 'product')
    def on_change_with_internal_quantity(self):
        pool = Pool()
        UoM = pool.get('product.uom')
        if self.quantity is not None and self.unit and self.product:
            return UoM.compute_qty(
                self.unit, self.quantity, self.product.default_uom, round=True)

    @fields.depends('from_location')
    def on_change_with_from_location_name(self, name=None):
        if self.from_location:
            return self.from_location.rec_name

    @fields.depends('to_location')
    def on_change_with_to_location_name(self, name=None):
        if self.to_location:
            return self.to_location.rec_name

    @classmethod
    def get_unit_price_company(cls, moves, name):
        pool = Pool()
        Currency = pool.get('currency.currency')
        Uom = pool.get('product.uom')
        Date = pool.get('ir.date')
        prices = {}
        for company, c_moves in groupby(moves, key=lambda m: m.company):
            with Transaction().set_context(company=company.id):
                today = Date.today()
            for move in c_moves:
                if move.unit_price is not None:
                    date = move.effective_date or move.planned_date or today
                    with Transaction().set_context(date=date):
                        unit_price = Currency.compute(
                            move.currency, move.unit_price,
                            move.company.currency, round=False)
                        unit_price = Uom.compute_price(
                            move.unit, unit_price, move.product.default_uom)
                        prices[move.id] = round_price(unit_price)
                else:
                    prices[move.id] = None
        return prices

    @fields.depends('from_location', 'to_location')
    def on_change_with_unit_price_required(self, name=None):
        from_type = self.from_location.type if self.from_location else None
        to_type = self.to_location.type if self.to_location else None

        if from_type == 'supplier' and to_type in {'storage', 'drop', 'view'}:
            return True
        if from_type == 'production' and to_type != 'lost_found':
            return True
        if from_type in {'storage', 'drop', 'view'} and to_type == 'customer':
            return True
        if from_type in {'storage', 'drop', 'view'} and to_type == 'supplier':
            return True
        if from_type == 'customer' and to_type in {'storage', 'drop', 'view'}:
            return True
        return False

    @fields.depends('from_location', 'to_location')
    def on_change_with_cost_price_required(self, name=None):
        from_type = self.from_location.type if self.from_location else None
        to_type = self.to_location.type if self.to_location else None
        return ((from_type != 'storage' and to_type == 'storage')
            or (from_type == 'storage' and to_type != 'storage')
            or (from_type != 'drop' and to_type == 'drop')
            or (from_type == 'drop' and to_type != 'drop'))

    @fields.depends('from_location', 'quantity')
    def on_change_with_assignation_required(self, name=None):
        if self.from_location:
            return (
                self.quantity
                and self.from_location.type in {'storage', 'view'})

    @classmethod
    def search_assignation_required(cls, name, clause):
        operators = {
            '=': 'in',
            '!=': 'not in',
            }
        reverse = {
            '=': '!=',
            '!=': '=',
            }
        if clause[1] in operators:
            if not clause[2]:
                operator = reverse[clause[1]]
            else:
                operator = clause[1]
            return [
                ('quantity', '!=', 0),
                ('from_location.type', operators[operator], [
                        'storage', 'view']),
                ]
        else:
            return []

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
        get_name = IrModel.get_name
        models = cls._get_shipment()
        return [(None, '')] + [(m, get_name(m)) for m in models]

    @classmethod
    def _get_origin(cls):
        'Return list of Model names for origin Reference'
        return [cls.__name__, 'stock.inventory.line']

    @classmethod
    def get_origin(cls):
        IrModel = Pool().get('ir.model')
        get_name = IrModel.get_name
        models = cls._get_origin()
        return [(None, '')] + [(m, get_name(m)) for m in models]

    @property
    def origin_name(self):
        if self.origin and self.origin.id >= 0:
            return self.origin.rec_name

    @classmethod
    @without_check_access
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
        return (lang.format_number_symbol(
                self.quantity, self.unit, digits=self.unit.digits)
            + ' %s' % self.product.rec_name)

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('product.rec_name',) + tuple(clause[1:])]

    def _compute_product_cost_price(self, direction, product_cost_price=None):
        """
        Update the cost price on the given product.
        The direction must be "in" if incoming and "out" if outgoing.
        """
        pool = Pool()
        Uom = pool.get('product.uom')

        if direction == 'in':
            quantity = self.quantity
        elif direction == 'out':
            quantity = -self.quantity
        qty = Uom.compute_qty(self.unit, quantity, self.product.default_uom)

        qty = Decimal(str(qty))
        product_qty = Decimal(str(self.product.quantity))
        unit_price = self.get_cost_price(product_cost_price=product_cost_price)
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

    def set_effective_date(self):
        pool = Pool()
        Date = pool.get('ir.date')
        ShipmentInternal = pool.get('stock.shipment.internal')

        if (not self.effective_date
                and isinstance(self.shipment, ShipmentInternal)
                and self.to_location == self.shipment.transit_location):
            self.effective_date = self.shipment.effective_start_date
        elif not self.effective_date and self.shipment:
            self.effective_date = self.shipment.effective_date
        if not self.effective_date:
            with Transaction().set_context(company=self.company.id):
                self.effective_date = Date.today()

        moves = [m for m in self.outcome_moves if m.state == 'done']
        if (isinstance(self.origin, self.__class__)
                and self.origin.state == 'done'):
            moves.append(self.origin)
        before_date = max(
            (m.effective_date for m in moves
                if m.to_location == self.from_location),
            default=datetime.date.min)
        if self.effective_date < before_date:
            self.effective_date = before_date
        after_date = min(
            (m.effective_date for m in moves
                if m.from_location == self.to_location),
            default=datetime.date.max)
        if self.effective_date > after_date:
            self.effective_date = after_date

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('/tree', 'visual', If(Eval('state') == 'cancelled', 'muted', '')),
            ('/tree/field[@name="delay"]', 'visual',
                If(Eval('delay', datetime.timedelta()) > TimeDelta(),
                    'danger', '')),
            ]

    @property
    def from_warehouse(self):
        pool = Pool()
        ShipmentInternal = pool.get('stock.shipment.internal')
        warehouse = self.from_location.warehouse
        if (not warehouse
                and isinstance(self.shipment, ShipmentInternal)
                and self.from_location == getattr(
                    self.shipment, 'transit_location', None)):
            warehouse = self.shipment.from_location.warehouse
        return warehouse

    @property
    def to_warehouse(self):
        pool = Pool()
        ShipmentInternal = pool.get('stock.shipment.internal')
        warehouse = self.to_location.warehouse
        if (not warehouse
                and isinstance(self.shipment, ShipmentInternal)
                and self.to_location == getattr(
                    self.shipment, 'transit_location', None)):
            warehouse = self.shipment.to_location.warehouse
        return warehouse

    @property
    def warehouse(self):
        return self.from_warehouse or self.to_warehouse

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, moves):
        cls.write(moves, {
                'effective_date': None,
                })

    @classmethod
    @Workflow.transition('assigned')
    def assign(cls, moves):
        cls.check_origin(moves)

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def do(cls, moves):
        pool = Pool()
        Product = pool.get('product.product')
        Date = pool.get('ir.date')
        Warning = pool.get('res.user.warning')
        today_cache = {}

        def in_future(move):
            if move.company not in today_cache:
                with Transaction().set_context(company=move.company.id):
                    today_cache[move.company] = Date.today()
            today = today_cache[move.company]
            if move.effective_date and move.effective_date > today:
                return move

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
                    move.set_effective_date()
                    previous_values = copy.copy(move._values)
                    cost_price, extra_to_save = move._do()
                    if cost_price is not None:
                        if move.product in products:
                            # The average computation of product cost price
                            # requires each previous move of the same product
                            # to be saved
                            cls.save(to_save)
                            set_cost_values(cost_values)
                            del to_save[:]
                            del cost_values[:]
                            products.clear()
                            # Recompute with unmodified move but including new
                            # saved moves
                            move._values = previous_values
                            cost_price, extra_to_save = move._do()
                        cost_values.append(
                            (move.product, cost_price,
                                move._cost_price_pattern))
                    to_save.extend(extra_to_save)
                    if move.cost_price_required and move.cost_price is None:
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

        future_moves = sorted(filter(in_future, moves))
        if future_moves:
            names = ', '.join(m.rec_name for m in future_moves[:5])
            if len(future_moves) > 5:
                names += '...'
            warning_name = Warning.format(
                'effective_date_future', future_moves)
            if Warning.check(warning_name):
                raise MoveFutureWarning(warning_name,
                    gettext('stock.msg_move_effective_date_in_the_future',
                        moves=names))

        replaced = set()
        for move in moves:
            if (move.product.replaced_by
                    and (move.from_location.type != 'storage'
                        or move.to_location.type != 'storage')):
                replaced.add(move.product)
        if replaced:
            Product.__queue__.deactivate_replaced(Product.browse(replaced))

    @property
    def _cost_price_pattern(self):
        return {
            'company': self.company.id,
            }

    def _cost_price_key(self):
        return (
            ('company', self.company.id),
            )

    def get_cost_price(self, product_cost_price=None):
        "Return the cost price of the move for computation"
        with Transaction().set_context(date=self.effective_date):
            if (self.from_location.type in {'supplier', 'production'}
                    or self.to_location.type == 'supplier'):
                return self.unit_price_company
            elif product_cost_price is not None:
                return product_cost_price
            elif self.cost_price is not None:
                return self.cost_price
            else:
                return self.product.get_multivalue(
                    'cost_price', **self._cost_price_pattern)

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
        with Transaction().set_context(company=moves[0].company.id):
            context['stock_date_end'] = Date.today()
        context['company'] = moves[0].company.id
        return context

    def _do(self):
        "Return cost_price and a list of moves to save"
        cost_price_method = self.product.get_multivalue(
            'cost_price_method', **self._cost_price_pattern)
        if (self.from_location.type in ('supplier', 'production')
                and self.to_location.type == 'storage'
                and cost_price_method == 'average'):
            return self._compute_product_cost_price('in'), []
        elif (self.to_location.type == 'supplier'
                and self.from_location.type == 'storage'
                and cost_price_method == 'average'):
            return self._compute_product_cost_price('out'), []
        return None, []

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, moves):
        pass

    @classmethod
    def copy(cls, moves, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('outcome_moves', None)
        return super().copy(moves, default=default)

    def compute_fields(self, field_names=None):
        cls = self.__class__
        values = super().compute_fields(field_names=field_names)
        if (not field_names
                or (cls.internal_quantity.on_change_with & field_names)):
            internal_quantity = self.on_change_with_internal_quantity()
            if getattr(self, 'internal_quantity', None) != internal_quantity:
                values['internal_quantity'] = internal_quantity
        return values

    @classmethod
    def preprocess_values(cls, mode, values):
        pool = Pool()
        Product = pool.get('product.product')
        context = Transaction().context
        values = super().preprocess_values(mode, values)
        if mode == 'create':
            assert values.get('state', cls.default_state()) in {
                'draft', 'staging'}
            if context.get('_product_replacement', True):
                product_id = values.get('product')
                if product_id is not None:
                    product = Product(product_id)
                    values['product'] = product.replacement.id
        elif mode == 'write':
            if {'unit_price', 'currency'} & values.keys():
                values['unit_price_updated'] = True
        return values

    @classmethod
    def check_modification(cls, mode, moves, values=None, external=False):
        super().check_modification(
            mode, moves, values=values, external=external)
        if mode == 'create':
            cls.check_period_closed(moves)
        elif mode == 'write':
            if values.keys() - cls._allow_modify_closed_period:
                cls.check_period_closed(moves)
            if values.keys() & cls._deny_modify_assigned:
                for move in moves:
                    if move.state == 'assigned':
                        raise AccessError(gettext(
                                'stock.msg_move_modify_assigned',
                                move=move.rec_name))
            if values.keys() & cls._deny_modify_done_cancel:
                for move in moves:
                    if move.state in {'done', 'cancelled'}:
                        raise AccessError(gettext(
                                'stock.msg_move_modify_%s' % move.state,
                                move=move.rec_name))
        elif mode == 'delete':
            for move in moves:
                if (move.state not in {'staging', 'draft', 'cancelled'}
                        and move.quantity):
                    raise AccessError(gettext(
                            'stock.msg_move_delete_draft_cancel',
                            move=move.rec_name))

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
        moves = sorted(filter(no_origin, moves))
        if moves:
            names = ', '.join(m.rec_name for m in moves[:5])
            if len(moves) > 5:
                names += '...'
            warning_name = Warning.format('done', moves)
            if Warning.check(warning_name):
                raise MoveOriginWarning(warning_name,
                    gettext('stock.msg_move_no_origin',
                        moves=names))

    def sort_quantities(self, quantities, locations, grouping):
        """
        Return the quantities ordered by pick preference which is the locations
        order by default.
        """
        locations = {l.id: i for i, l in enumerate(locations)}
        quantities = filter(lambda x: x[0][0] in locations, quantities)
        return sorted(quantities, key=lambda x: locations[x[0][0]])

    def pick_product(self, quantities):
        """
        Pick the product across the keys. Naive (fast) implementation.
        Return a list of tuple (key, quantity) for quantities that can be
        picked.
        """
        to_pick = []
        needed_qty = self.quantity
        for key, available_qty in quantities:
            # Ignore available_qty when too small
            if available_qty < self.unit.rounding:
                continue
            if needed_qty <= available_qty:
                to_pick.append((key, needed_qty))
                return to_pick
            else:
                to_pick.append((key, available_qty))
                needed_qty -= available_qty
        if default_location := self._default_pick_location:
            to_pick.append(((default_location,), needed_qty))
            return to_pick
        return to_pick

    @property
    def _default_pick_location(self):
        "The location to pick by default"
        # Force assignation for consumables:
        if self.product.consumable and self.from_location.type != 'view':
            return self.from_location

    @classmethod
    def assign_try(
            cls, moves, with_childs=True, grouping=('product',), pblc=None):
        '''
        Try to assign moves.
        It uses pblc as product by location by company if provided otherwise it
        computes based on today.
        It will split the moves to assign as much possible.
        Return True if succeed or False if not.
        '''
        pool = Pool()
        Product = pool.get('product.product')
        Uom = pool.get('product.uom')
        Date = pool.get('ir.date')
        Location = pool.get('stock.location')

        moves = [m for m in moves if m.state in {'draft', 'staging'}]
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
        stock_date_end = Date.today()

        if pblc is None:
            pblc = {}
            companies = {m.company for m in moves}
            for company in companies:
                with Transaction().set_context(company=company.id):
                    stock_date_end = Date.today()

                cls._assign_try_lock(
                    product_ids, location_ids, [company.id],
                    stock_date_end, grouping)

                with Transaction().set_context(
                        stock_date_end=stock_date_end,
                        stock_assign=True,
                        company=company.id):
                    pblc[company.id] = Product.products_by_location(
                        location_ids,
                        grouping=grouping,
                        grouping_filter=(product_ids,))

        def get_key(move, location_id):
            key = (location_id,)
            for field in grouping:
                value = getattr(move, field)
                if isinstance(value, Model):
                    value = value.id
                key += (value,)
            return key

        def get_values(key, location_name):
            yield location_name, key[0]
            for field, value in zip(grouping, key[1:]):
                if value is not None and '.' not in field:
                    yield field, value

        def match(key, pattern):
            for k, p in zip(key, pattern):
                if p is None or k == p:
                    continue
                else:
                    return False
            else:
                return True

        def default_values(values):
            def get_value(name):
                def get_default(data):
                    return values[data['id']].get(name, data[name])
                return get_default
            default = {}
            for name in set().union(*(v.keys() for v in values.values())):
                default[name] = get_value(name)
            return default

        child_locations = {}
        to_write = []
        to_assign = []
        to_copy = defaultdict(list)
        success = True
        for move in moves:
            if move.state != 'draft':
                if move.state == 'staging':
                    success = False
                continue
            pbl = pblc[move.company.id]
            # Keep location order for pick_product
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
            # Prevent picking from the destination location
            try:
                childs.remove(move.to_location)
            except ValueError:
                pass
            # Try first to pick from source location
            try:
                childs.remove(move.from_location)
                childs.insert(0, move.from_location)
            except ValueError:
                # from_location may be a view
                pass
            location_qties = []
            for key, qty in pbl.items():
                move_key = get_key(move, key[0])
                if match(key, move_key):
                    qty = Uom.compute_qty(
                        move.product.default_uom, qty, move.unit,
                        round=False)
                    location_qties.append((key, qty))

            location_qties = move.sort_quantities(
                location_qties, childs, grouping)
            to_pick = move.pick_product(location_qties)

            picked_qties = 0.0
            for _, qty in to_pick:
                picked_qties += qty

            if move.quantity - picked_qties >= move.unit.rounding:
                success = False
                first = False
                values = {
                    'quantity': move.unit.round(
                        move.quantity - picked_qties),
                    }
                to_write.extend([[move], values])
            else:
                first = True
            for key, qty in to_pick:
                values = dict(get_values(key, 'from_location'))
                values['quantity'] = move.unit.round(qty)
                if first:
                    to_write.extend([[move], values])
                    to_assign.append(move)
                    first = False
                else:
                    to_copy[move].append(values)

                qty_default_uom = Uom.compute_qty(
                    move.unit, qty, move.product.default_uom, round=False)

                pbl[key] = pbl.get(key, 0.0) - qty_default_uom

        with Transaction().set_context(_stock_move_split=True):
            while to_copy:
                moves_to_copy = []
                values = {}
                for move, vlist in list(to_copy.items()):
                    if vlist:
                        moves_to_copy.append(move)
                        values[move.id] = vlist.pop(0)
                    else:
                        del to_copy[move]
                to_assign.extend(cls.copy(
                        moves_to_copy,
                        default=default_values(values)))
        if to_write:
            cls.write(*to_write)
        if to_assign:
            cls.assign(to_assign)
        return success

    @classmethod
    def _assign_try_lock(
            cls, product_ids, location_ids, company_ids, date, grouping):
        """Lock the database to prevent concurrent assignation"""
        pool = Pool()
        Period = pool.get('stock.period')
        transaction = Transaction()
        database = transaction.database
        connection = transaction.connection

        if database.has_select_for():
            count = database.IN_MAX // 2
            PeriodCache = Period.get_cache(grouping)
            with connection.cursor() as cursor:
                for company_id in company_ids:
                    period = None
                    if PeriodCache:
                        periods = Period.search([
                                ('date', '<', date),
                                ('company', '=', company_id),
                                ('state', '=', 'closed'),
                                ], order=[('date', 'DESC')], limit=1)
                        if periods:
                            period, = periods
                    for sub_location_ids in grouped_slice(location_ids, count):
                        sub_location_ids = list(sub_location_ids)
                        table = cls.__table__()
                        query = table.select(Literal(1),
                            where=(reduce_ids(
                                    table.to_location, sub_location_ids)
                                | reduce_ids(
                                    table.from_location, sub_location_ids))
                            & table.product.in_(product_ids)
                            & (table.company == company_id),
                            for_=For('UPDATE', nowait=True))

                        if period:
                            query.where &= Coalesce(
                                table.effective_date,
                                table.planned_date,
                                datetime.date.max) > period.date
                        cursor.execute(*query)
        else:
            cls.lock()

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
            stock_invert: if set invert the quantity.
        If with_childs, it computes also for child locations.
        grouping is a tuple of Move (or Product if prefixed by 'product.' or
            'date') field names and defines how stock moves are grouped.
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
        transaction = Transaction()

        if not location_ids:
            return None
        context = transaction.context.copy()

        use_product = False
        for field in grouping:
            if field.startswith('product.'):
                Model = Product
                field = field[len('product.'):]
                use_product = True
            else:
                Model = Move
            if field not in Model._fields and field != 'date':
                raise ValueError('"%s" has no field "%s"' % (Model, field))
        assert grouping_filter is None or len(grouping_filter) <= len(grouping)
        assert len(set(grouping)) == len(grouping)
        assert ('stock_date_start' in context) if 'date' in grouping else True

        company = User(transaction.user).company

        def get_column(name, table):
            if name == 'date':
                return cls.effective_date.sql_cast(
                    Coalesce(
                        table.effective_date,
                        Case((move.state == 'assigned', today), else_=Null),
                        table.planned_date))
            else:
                return Column(table, name)

        def get_column_product(name, table, product):
            if name.startswith('product.'):
                column = Column(product, name[len('product.'):])
            else:
                column = Column(table, name)
            return column.as_(name)

        if use_product:
            product = Product.__table__()
            columns = ['id', 'state', 'effective_date', 'planned_date',
            'internal_quantity', 'from_location', 'to_location', 'company']
            columns += [
                c for c in grouping if c not in columns and c != 'date']
            columns = [get_column_product(c, move, product) for c in columns]
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
                columns = [
                    get_column_product(c, period_cache, product_cache)
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
            columns = [get_column(c, move).as_(c) for c in columns]

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

        move_date = Coalesce(
            move.effective_date,
            Case((move.state == 'assigned', today), else_=Null),
            move.planned_date)

        # date end in the past or today: filter on state done
        if (context['stock_date_end'] < today
                or (context['stock_date_end'] == today
                    and not context.get('forecast'))):

            def state_date_clause(stock_assign):
                return (move.state.in_(['done',
                        'assigned' if stock_assign else 'done'])
                    & (move_date <= context['stock_date_end']))
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
                        & (move_date <= today))
                    | (move.state.in_(['done', 'assigned', 'draft'])
                        & (Coalesce(move_date, datetime.date.max)
                            <= context['stock_date_end'])
                        & (Coalesce(move_date, datetime.date.max) >= today)
                        ))
            state_date_clause_in = state_date_clause(False)
            state_date_clause_out = state_date_clause(
                context.get('stock_assign'))

        if context.get('stock_date_start'):
            if context['stock_date_start'] > today:
                def state_date_clause():
                    return (move.state.in_(['done', 'assigned', 'draft'])
                        & (Coalesce(move_date, datetime.date.max)
                            >= context['stock_date_start'])
                        )
                state_date_clause_in &= state_date_clause()
                state_date_clause_out &= state_date_clause()
            else:
                def state_date_clause(stock_assign):
                    return ((
                            move.state.in_(['done', 'assigned', 'draft'])
                            & (Coalesce(move_date, datetime.date.max) >= today)
                            )
                        | (
                            move.state.in_(['done',
                                    'assigned' if stock_assign else 'done'])
                            & (Coalesce(move_date, datetime.date.max)
                                >= context['stock_date_start'])
                            & (Coalesce(move_date, datetime.date.min) < today)
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
                    return (
                        Coalesce(
                            move.effective_date,
                            move.planned_date,
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
                column = get_column(fieldname, move)
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
        move_keys_alias = [get_column(key, move).as_(key) for key in grouping]
        move_keys = [get_column(key, move) for key in grouping]

        if company:
            company_clause = move.company == company.id
        elif not transaction.user:
            company_clause = Literal(True)
        else:
            company_clause = Literal(False)
        query = move.select(move.to_location.as_('location'),
            Sum(move.internal_quantity).as_('quantity'),
            *move_keys_alias,
            where=state_date_clause_in
            & where
            & move.to_location.in_(location_query)
            & company_clause
            & dest_clause_from,
            group_by=[move.to_location] + move_keys)
        query = Union(query, move.select(move.from_location.as_('location'),
                (-Sum(move.internal_quantity)).as_('quantity'),
                *move_keys_alias,
                where=state_date_clause_out
                & where
                & move.from_location.in_(location_query)
                & company_clause
                & dest_clause_to,
                group_by=[move.from_location] + move_keys),
            all_=True)
        if PeriodCache and period:
            period_keys = [Column(period_cache, key).as_(key)
                for key in grouping]
            query = Union(query, from_period.select(
                    period_cache.location.as_('location'),
                    period_cache.internal_quantity.as_('quantity'),
                    *period_keys,
                    where=(period_cache.period == period.id)
                    & where_period
                    & period_cache.location.in_(location_query)
                    & dest_clause_period),
                all_=True)
        query_keys = [Column(query, key).as_(key) for key in grouping]
        quantity = Sum(query.quantity)
        if context.get('stock_invert'):
            quantity *= -1
        columns = ([query.location.as_('location')]
            + query_keys
            + [quantity.as_('quantity')])
        query = query.select(*columns,
            group_by=[query.location] + query_keys)
        return query

    @classmethod
    def compute_quantities(cls, query, location_ids, with_childs=False,
            grouping=('product',), grouping_filter=None):
        """
        Executes the supplied query to compute for each location and product
        the stock quantity in the default uom of the product and rounded to
        UoM's rounding digits.

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
        for line in cursor:
            if len(location_ids) > 1:
                location = line[0]
            key = list(line[1:-1])
            if 'date' in grouping:
                i = grouping.index('date')
                if key[i] and not isinstance(key[i], datetime.date):
                    key[i] = datetime.date.fromisoformat(key[i])
            key = tuple(key)
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
            parents = {}
            for location in locations:
                parent = location.parent
                if not parent or parent.flat_childs:
                    continue
                if parent.id in leafs:
                    leafs.remove(parent.id)
                # Group children under the common requested grand parent
                # to skip unnecessary intermediary result
                while parent:
                    parents[location.id] = parent.id
                    if parent.id in location_ids:
                        break
                    parent = parent.parent
            locations = set((l.id for l in locations))
            while leafs:
                for leaf in leafs:
                    locations.remove(leaf)
                    if leaf not in parents:
                        continue
                    parent = parents[leaf]
                    for key in keys:
                        quantities[(parent, *key)] += quantities[(leaf, *key)]
                next_leafs = set(locations)
                for location in locations:
                    parent = parents.get(location)
                    if not parent:
                        continue
                    if parent in next_leafs and parent in locations:
                        next_leafs.remove(parent)
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
