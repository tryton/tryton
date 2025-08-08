# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from collections import defaultdict
from copy import copy

from sql import Cast, Column, Null
from sql.conditionals import Case
from sql.functions import CharLength
from sql.operators import Concat

from trytond.i18n import gettext
from trytond.model import (
    DeactivableMixin, Index, Model, ModelSQL, ModelView, fields)
from trytond.model.exceptions import (
    AccessError, RequiredValidationError, ValidationError)
from trytond.modules.stock import StockMixin
from trytond.modules.stock.exceptions import ShipmentCheckQuantityWarning
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, If, Len
from trytond.tools import grouped_slice
from trytond.transaction import Transaction
from trytond.wizard import Button, StateTransition, StateView, Wizard


class LotMixin:
    __slots__ = ()
    number = fields.Char(
        "Number", required=True,
        states={
            'required': ~Eval('has_sequence') | (Eval('id', -1) >= 0),
            })
    product = fields.Many2One('product.product', 'Product', required=True)
    has_sequence = fields.Function(
        fields.Boolean("Has Sequence"), 'on_change_with_has_sequence')

    @classmethod
    def __setup__(cls):
        cls.number.search_unaccented = False
        super().__setup__()

    @fields.depends('product')
    def on_change_with_has_sequence(self, name=None):
        if self.product:
            return bool(self.product.lot_sequence)


class Lot(DeactivableMixin, ModelSQL, ModelView, LotMixin, StockMixin):
    __name__ = 'stock.lot'
    _rec_name = 'number'

    quantity = fields.Function(
        fields.Float("Quantity", digits='default_uom'),
        'get_quantity', searcher='search_quantity')
    forecast_quantity = fields.Function(
        fields.Float("Forecast Quantity", digits='default_uom'),
        'get_quantity', searcher='search_quantity')
    default_uom = fields.Function(
        fields.Many2One(
            'product.uom', "Default UoM",
            help="The default Unit of Measure."),
        'on_change_with_default_uom', searcher='search_default_uom')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._modify_no_move = [
            ('product', None, 'stock_lot.msg_change_product'),
            ]
        cls._buttons.update({
                'upward_traces': {},
                'downward_traces': {},
                })

    @classmethod
    def order_number(cls, tables):
        table, _ = tables[None]
        return [CharLength(table.number), table.number]

    @classmethod
    def get_quantity(cls, lots, name):
        location_ids = Transaction().context.get('locations')
        product_ids = list(set(l.product.id for l in lots))
        quantities = {}
        for product_ids in grouped_slice(product_ids):
            quantities.update(cls._get_quantity(lots, name, location_ids,
                    grouping=('product', 'lot',),
                    grouping_filter=(list(product_ids),)))
        return quantities

    @classmethod
    def search_quantity(cls, name, domain=None):
        location_ids = Transaction().context.get('locations')
        return cls._search_quantity(name, location_ids, domain,
            grouping=('product', 'lot'))

    @fields.depends('product')
    def on_change_with_default_uom(self, name=None):
        return self.product.default_uom if self.product else None

    @classmethod
    def search_default_uom(cls, name, clause):
        nested = clause[0][len(name):]
        return [('product.' + name + nested, *clause[1:])]

    @classmethod
    def copy(cls, lots, default=None):
        default = default.copy() if default else {}
        has_sequence = {l.id: l.has_sequence for l in lots}
        default.setdefault(
            'number', lambda o: None if has_sequence[o['id']] else o['number'])
        return super().copy(lots, default=default)

    @classmethod
    def preprocess_values(cls, mode, values):
        pool = Pool()
        Product = pool.get('product.product')
        values = super().preprocess_values(mode, values)
        if mode == 'create' and not values.get('number'):
            product_id = values.get('product')
            if product_id is not None:
                product = Product(product_id)
                if product.lot_sequence:
                    values['number'] = product.lot_sequence.get()
        return values

    @classmethod
    def check_modification(cls, mode, lots, values=None, external=False):
        pool = Pool()
        Move = pool.get('stock.move')
        transaction = Transaction()

        def find_moves(cls, state=None):
            for sub_records in grouped_slice(lots):
                domain = [
                    ('lot', 'in', [r.id for r in sub_records])
                    ]
                if state:
                    domain.append(('state', '=', state))
                moves = Move.search(domain, limit=1, order=[])
                if moves:
                    return True
            return False

        super().check_modification(
            mode, lots, values=values, external=external)
        if mode == 'write':
            if transaction.user and transaction.check_access:
                for field, state, error in cls._modify_no_move:
                    if field in values:
                        if find_moves(state):
                            raise AccessError(gettext(error))
                        # No moves
                        break

    @classmethod
    @ModelView.button_action('stock_lot.act_lot_trace_upward_relate')
    def upward_traces(cls, lots):
        pass

    @classmethod
    @ModelView.button_action('stock_lot.act_lot_trace_downward_relate')
    def downward_traces(cls, lots):
        pass


class LotTrace(ModelSQL, ModelView):
    __name__ = 'stock.lot.trace'
    product = fields.Many2One(
        'product.product', "Product",
        context={
            'company': Eval('company', -1),
            },
        depends=['company'])
    lot = fields.Many2One('stock.lot', "Lot")

    from_location = fields.Many2One('stock.location', "From Location")
    to_location = fields.Many2One('stock.location', "To Location")

    quantity = fields.Float("Quantity", digits='unit')
    unit = fields.Many2One('product.uom', "Unit")

    company = fields.Many2One('company.company', "Company")
    date = fields.Date("Date")
    document = fields.Reference("Document", 'get_documents')

    upward_traces = fields.Function(
        fields.Many2Many(
            'stock.lot.trace', None, None, "Upward Traces"),
        'get_upward_traces')
    downward_traces = fields.Function(
        fields.Many2Many(
            'stock.lot.trace', None, None, "Downward Traces"),
        'get_downward_traces')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('date', None))

    @classmethod
    def table_query(cls):
        from_item, tables = cls._joins()
        query = from_item.select(
            *cls._columns(tables),
            where=cls._where(tables))
        return query

    @classmethod
    def _joins(cls):
        pool = Pool()
        Move = pool.get('stock.move')
        InventoryLine = pool.get('stock.inventory.line')

        move = Move.__table__()
        inventory_line = InventoryLine.__table__()
        tables = {}
        tables['move'] = move
        tables['inventory_line'] = inventory_line

        inventory_line_id = Move.origin.sql_id(move.origin, Move)
        from_item = (move.join(inventory_line, type_='LEFT',
            condition=(move.origin.like(InventoryLine.__name__ + '%')
                & (inventory_line.id == inventory_line_id))))
        return from_item, tables

    @classmethod
    def _where(cls, tables):
        move = tables['move']
        return (move.lot != Null) & (move.state == 'done')

    @classmethod
    def _columns(cls, tables):
        move = tables['move']
        return [
            move.id.as_('id'),
            move.product.as_('product'),
            move.lot.as_('lot'),
            move.from_location.as_('from_location'),
            move.to_location.as_('to_location'),
            move.quantity.as_('quantity'),
            move.unit.as_('unit'),
            move.company.as_('company'),
            move.effective_date.as_('date'),
            cls.get_document(tables).as_('document'),
            ]

    def get_rec_name(self, name):
        return self.document.rec_name if self.document else str(self.id)

    @classmethod
    def get_documents(cls):
        pool = Pool()
        Model = pool.get('ir.model')
        Move = pool.get('stock.move')
        return Move.get_origin() + [
            ('stock.inventory', Model.get_name('stock.inventory'))]

    @classmethod
    def get_document(cls, tables):
        move = tables['move']
        inventory_line = tables['inventory_line']
        sql_type = cls.document.sql_type().base
        return Case(
            ((inventory_line.id != Null),
            Concat('stock.inventory,',
                Cast(inventory_line.inventory, sql_type))),
            else_=move.shipment)

    @classmethod
    def _is_trace_move(cls, move):
        return move.state == 'done'

    @classmethod
    def _trace_move_order_key(cls, move):
        return (move.effective_date, move.id)

    def get_upward_traces(self, name):
        return list(map(int, sorted(filter(
                        self._is_trace_move, self._get_upward_traces()),
                    key=self._trace_move_order_key)))

    def _get_upward_traces(self):
        pool = Pool()
        Move = pool.get('stock.move')
        return set(Move.search([
                    ('lot', '=', self.lot.id),
                    ('from_location', '=', self.to_location),
                    ('effective_date', '>=', self.date),
                    ]))

    def get_downward_traces(self, name):
        return list(map(int, sorted(filter(
                        self._is_trace_move, self._get_downward_traces()),
                    key=self._trace_move_order_key, reverse=True)))

    def _get_downward_traces(self):
        pool = Pool()
        Move = pool.get('stock.move')
        return set(Move.search([
                    ('lot', '=', self.lot.id),
                    ('to_location', '=', self.from_location),
                    ('effective_date', '<=', self.date),
                    ]))


class LotByLocationContext(ModelView):
    __name__ = 'stock.lots_by_location.context'
    forecast_date = fields.Date(
        'At Date', help=('Allow to compute expected '
            'stock quantities for this date.\n'
            '* An empty value is an infinite date in the future.\n'
            '* A date in the past will provide historical values.'))
    stock_date_end = fields.Function(fields.Date('At Date'),
        'on_change_with_stock_date_end')

    @staticmethod
    def default_forecast_date():
        Date = Pool().get('ir.date')
        return Date.today()

    @fields.depends('forecast_date')
    def on_change_with_stock_date_end(self, name=None):
        if self.forecast_date is None:
            return datetime.date.max
        return self.forecast_date


class LotsByLocations(ModelSQL, ModelView):
    __name__ = 'stock.lots_by_locations'

    lot = fields.Many2One('stock.lot', "Lot")
    product = fields.Many2One('product.product', "Product")
    quantity = fields.Function(
        fields.Float("Quantity", digits='default_uom'),
        'get_lot', searcher='search_lot')
    forecast_quantity = fields.Function(
        fields.Float("Forecast Quantity", digits='default_uom'),
        'get_lot', searcher='search_lot')
    default_uom = fields.Function(
        fields.Many2One(
            'product.uom', "Default UoM",
            help="The default Unit of Measure."),
        'get_lot', searcher='search_lot')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('lot', 'ASC'))
        cls._order.insert(1, ('product', 'ASC'))

    @classmethod
    def table_query(cls):
        pool = Pool()
        Lot = pool.get('stock.lot')
        lot = Lot.__table__()
        columns = []
        for fname, field in cls._fields.items():
            if not hasattr(field, 'set'):
                if (isinstance(field, fields.Many2One)
                        and field.get_target() == Lot):
                    column = Column(lot, 'id')
                else:
                    column = Column(lot, fname)
                columns.append(column.as_(fname))
        return lot.select(*columns)

    def get_rec_name(self, name):
        return self.lot.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('lot.rec_name',) + tuple(clause[1:])]

    def get_lot(self, name):
        value = getattr(self.lot, name)
        if isinstance(value, Model):
            value = value.id
        return value

    @classmethod
    def search_lot(cls, name, clause):
        nested = clause[0][len(name):]
        return [('lot.' + name + nested, *clause[1:])]


class Location(metaclass=PoolMeta):
    __name__ = 'stock.location'

    @classmethod
    def _get_quantity_grouping(cls):
        pool = Pool()
        Lot = pool.get('stock.lot')
        context = Transaction().context
        grouping, grouping_filter, key = super()._get_quantity_grouping()
        if context.get('lot') is not None:
            try:
                lot, = Lot.search([('id', '=', context['lot'])])
            except ValueError:
                pass
            else:
                grouping = ('product', 'lot',)
                grouping_filter = ([lot.product.id], [lot.id])
                key = (lot.product.id, lot.id)
        return grouping, grouping_filter, key


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'
    lot = fields.Many2One(
        'stock.lot', "Lot", ondelete='RESTRICT',
        domain=[
            ('product', '=', Eval('product', -1)),
            ],
        states={
            'readonly': Eval('state').in_(['cancelled', 'done']),
            },
        search_context={
            'locations': If(Eval('from_location'),
                [Eval('from_location', -1)], []),
            'stock_date_end': (
                If(Eval('effective_date'),
                    Eval('effective_date', None),
                    Eval('planned_date', None))),
            })

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._deny_modify_done_cancel.add('lot')
        cls._buttons.update({
                'add_lots_wizard': {
                    'invisible': ~Eval('state').in_(['draft', 'assigned']),
                    'readonly': Bool(Eval('lot')),
                    'depends': ['lot', 'state'],
                    },
                })

    @classmethod
    @ModelView.button_action('stock_lot.wizard_move_add_lots')
    def add_lots_wizard(cls, moves):
        pass

    def add_lot(self):
        if not self.lot and self.product:
            lot = self.product.create_lot()
            if lot:
                self.lot = lot

    def check_lot(self):
        "Check if lot is required"
        if (self.internal_quantity
                and not self.lot
                and self.product.lot_is_required(
                    self.from_location, self.to_location)):
            raise RequiredValidationError(
                gettext('stock_lot.msg_lot_required',
                    product=self.product.rec_name))

    @classmethod
    @ModelView.button
    def do(cls, moves):
        super().do(moves)
        for move in moves:
            move.check_lot()

    @classmethod
    def assign_try(
            cls, moves, with_childs=True, grouping=('product',), pblc=None):
        if 'lot' not in grouping:
            moves_with_lot, moves_without_lot = [], []
            for move in moves:
                if move.lot:
                    moves_with_lot.append(move)
                else:
                    moves_without_lot.append(move)
            success = super().assign_try(
                moves_with_lot, with_childs=with_childs,
                grouping=grouping + ('lot',), pblc=pblc)
            success &= super().assign_try(
                moves_without_lot, with_childs=with_childs,
                grouping=grouping, pblc=pblc)
        else:
            success = super().assign_try(
                moves, with_childs=with_childs, grouping=grouping, pblc=pblc)
        return success

    @fields.depends('product', 'lot')
    def on_change_product(self):
        try:
            super().on_change_product()
        except AttributeError:
            pass
        if self.lot and self.lot.product != self.product:
            self.lot = None


class MoveAddLots(Wizard):
    __name__ = 'stock.move.add.lots'
    start = StateView('stock.move.add.lots.start',
        'stock_lot.move_add_lots_start_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Add", 'add', 'tryton-ok', default=True),
            ])
    add = StateTransition()

    def default_start(self, fields):
        default = {}
        if 'product' in fields:
            default['product'] = self.record.product.id
        if 'quantity' in fields:
            default['quantity'] = self.record.quantity
        if 'unit' in fields:
            default['unit'] = self.record.unit.id
        return default

    def transition_add(self):
        pool = Pool()
        Lang = pool.get('ir.lang')
        Lot = pool.get('stock.lot')
        lang = Lang.get()
        quantity_remaining = self.start.on_change_with_quantity_remaining()
        if quantity_remaining < 0:
            digits = self.record.unit.digits
            move_quantity = self.record.quantity
            lot_quantity = self.record.quantity - quantity_remaining
            raise ValidationError(gettext(
                    'stock_lot.msg_move_add_lot_quantity',
                    lot_quantity=lang.format_number(lot_quantity, digits),
                    move_quantity=lang.format_number(move_quantity, digits)))
        lots = []
        for line in self.start.lots:
            lot = line.get_lot(self.record)
            lots.append(lot)
        Lot.save(lots)
        if hasattr(self.model, 'split'):
            move = self.record
            for line, lot in zip(self.start.lots, lots):
                splits = move.split(line.quantity, self.record.unit, count=1)
                splits.remove(move)
                move.lot = lot
                move.save()
                if splits:
                    move, = splits
                else:
                    break
        else:
            if quantity_remaining:
                self.record.quantity = quantity_remaining
                self.record.save()
            for i, (line, lot) in enumerate(zip(self.start.lots, lots)):
                if not i and not quantity_remaining:
                    self.record.quantity = line.quantity
                    self.record.lot = lot
                    self.record.save()
                else:
                    with Transaction().set_context(_stock_move_split=True):
                        self.model.copy([self.record], {
                                'quantity': line.quantity,
                                'lot': lot.id,
                                })
        return 'end'


class MoveAddLotsStart(ModelView):
    __name__ = 'stock.move.add.lots.start'

    product = fields.Many2One('product.product', "Product", readonly=True)
    quantity = fields.Float("Quantity", digits='unit', readonly=True)
    unit = fields.Many2One('product.uom', "Unit", readonly=True)
    quantity_remaining = fields.Function(
        fields.Float("Quantity Remaining", digits='unit'),
        'on_change_with_quantity_remaining')

    lots = fields.One2Many(
        'stock.move.add.lots.start.lot', 'parent', "Lots",
        domain=[
            ('product', '=', Eval('product', -1)),
            ],
        states={
            'readonly': ~Eval('quantity_remaining', 0),
            })

    duplicate_lot_number = fields.Integer(
        "Duplicate Lot Number",
        states={
            'invisible': Len(Eval('lots')) != 1,
            },
        help="The number of times the lot must be duplicated.")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update(
            duplicate_lot={
                'invisible': Len(Eval('lots')) != 1,
                'readonly': (~Eval('duplicate_lot_number')
                    | (Eval('duplicate_lot_number', 0) <= 0)),
                'depends': ['lots', 'duplicate_lot_number'],
                },
            )

    @fields.depends('quantity', 'lots', 'unit')
    def on_change_with_quantity_remaining(self, name=None):
        if self.quantity is not None:
            quantity = self.quantity
            if self.lots:
                for lot in self.lots:
                    quantity -= getattr(lot, 'quantity', 0) or 0
            if self.unit:
                quantity = self.unit.round(quantity)
            return quantity

    @ModelView.button_change(
        'lots', 'duplicate_lot_number',
        methods=['on_change_with_quantity_remaining'])
    def duplicate_lot(self):
        lots = list(self.lots)
        if self.lots:
            template, = self.lots
            for i in range(self.duplicate_lot_number):
                lot = copy(template)
                lot._id = None
                lots.append(lot)
        self.lots = lots
        self.quantity_remaining = self.on_change_with_quantity_remaining()


class MoveAddLotsStartLot(ModelView, LotMixin):
    __name__ = 'stock.move.add.lots.start.lot'

    parent = fields.Many2One('stock.move.add.lots.start', "Parent")
    quantity = fields.Float("Quantity", digits='quantity_unit', required=True)
    quantity_unit = fields.Function(
        fields.Many2One('product.uom', "Unit"), 'on_change_with_quantity_unit')

    @fields.depends(
        'parent', '_parent_parent.quantity_remaining')
    def on_change_parent(self):
        if (self.parent
                and self.parent.quantity_remaining is not None):
            self.quantity = self.parent.quantity_remaining

    @fields.depends('parent', '_parent_parent.unit')
    def on_change_with_quantity_unit(self, name=None):
        if self.parent and self.parent.unit:
            return self.parent.unit.id

    @fields.depends('number', 'product', methods=['_set_lot_values'])
    def on_change_number(self):
        pool = Pool()
        Lot = pool.get('stock.lot')
        if self.number and self.product:
            lots = Lot.search([
                    ('number', '=', self.number),
                    ('product', '=', self.product.id),
                    ])
            if len(lots) == 1:
                lot, = lots
                self._set_lot_values(lot)

    def _set_lot_values(self, lot):
        pass

    def get_lot(self, move):
        pool = Pool()
        Lot = pool.get('stock.lot')
        values = self._get_lot_values(move)
        lots = Lot.search(
            [(k, '=', v) for k, v in values.items()],
            limit=1)
        if lots:
            lot, = lots
        else:
            lot = Lot()
            for k, v in values.items():
                setattr(lot, k, v)
        return lot

    def _get_lot_values(self, move):
        return {
            'number': self.number,
            'product': move.product,
            }


class ShipmentCheckQuantity:
    "Check quantities per lot between source and target moves"
    __slots__ = ()

    def check_quantity(self):
        pool = Pool()
        Warning = pool.get('res.user.warning')
        Lang = pool.get('ir.lang')
        lang = Lang.get()

        super().check_quantity()

        products_with_lot = set()
        source_qties = defaultdict(float)
        for move in self._check_quantity_source_moves:
            if move.lot:
                products_with_lot.add(move.product)
                source_qties[move.lot] += move.internal_quantity

        target_qties = defaultdict(float)
        for move in self._check_quantity_target_moves:
            if move.lot:
                target_qties[move.lot] += move.internal_quantity

        diffs = {}
        for lot, incoming_qty in target_qties.items():
            if (lot not in source_qties
                    and lot.product not in products_with_lot):
                continue
            unit = lot.product.default_uom
            incoming_qty = unit.round(incoming_qty)
            inventory_qty = unit.round(source_qties.pop(lot, 0))
            diff = inventory_qty - incoming_qty
            if diff:
                diffs[lot] = diff

        if diffs:
            warning_name = Warning.format(
                'check_quantity_lot', [self])
            if Warning.check(warning_name):
                quantities = []
                for lot, quantity in diffs.items():
                    quantity = lang.format_number_symbol(
                        quantity, lot.product.default_uom)
                    quantities.append(f"{lot.rec_name}: {quantity}")
                raise ShipmentCheckQuantityWarning(warning_name,
                    gettext(
                        'stock.msg_shipment_check_quantity',
                        shipment=self.rec_name,
                        quantities=', '.join(quantities)))


class ShipmentIn(ShipmentCheckQuantity, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in'

    def _get_inventory_move(self, incoming_move):
        move = super()._get_inventory_move(incoming_move)
        if move and incoming_move.lot:
            move.lot = incoming_move.lot
        return move


class ShipmentOut(ShipmentCheckQuantity, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    def _get_inventory_move(self, outgoing_move):
        move = super()._get_inventory_move(outgoing_move)
        if move and outgoing_move.lot:
            move.lot = outgoing_move.lot
        return move

    def _sync_move_key(self, move):
        return super()._sync_move_key(move) + (('lot', move.lot),)


class ShipmentOutReturn(ShipmentCheckQuantity, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.return'

    def _get_inventory_move(self, incoming_move):
        move = super()._get_inventory_move(incoming_move)
        if move and incoming_move.lot:
            move.lot = incoming_move.lot
        return move


class ShipmentInternal(ShipmentCheckQuantity, metaclass=PoolMeta):
    __name__ = 'stock.shipment.internal'

    def _sync_move_key(self, move):
        return super()._sync_move_key(move) + (('lot', move.lot),)


class ShipmentDrop(ShipmentCheckQuantity, metaclass=PoolMeta):
    __name__ = 'stock.shipment.drop'

    def _sync_move_key(self, move):
        return super()._sync_move_key(move) + (('lot', move.lot),)


class Period(metaclass=PoolMeta):
    __name__ = 'stock.period'
    lot_caches = fields.One2Many('stock.period.cache.lot', 'period',
        'Lot Caches', readonly=True)

    @classmethod
    def groupings(cls):
        return super().groupings() + [('product', 'lot')]

    @classmethod
    def get_cache(cls, grouping):
        pool = Pool()
        Cache = super().get_cache(grouping)
        if grouping == ('product', 'lot'):
            return pool.get('stock.period.cache.lot')
        return Cache


class PeriodCacheLot(ModelSQL, ModelView):
    "It is used to store cached computation of stock quantities per lot"
    __name__ = 'stock.period.cache.lot'

    period = fields.Many2One(
        'stock.period', "Period",
        required=True, readonly=True, ondelete='CASCADE')
    location = fields.Many2One(
        'stock.location', "Location",
        required=True, readonly=True, ondelete='CASCADE')
    product = fields.Many2One('product.product', 'Product', required=True,
        readonly=True, ondelete='CASCADE')
    lot = fields.Many2One('stock.lot', 'Lot', readonly=True,
        ondelete='CASCADE')
    internal_quantity = fields.Float('Internal Quantity', readonly=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_indexes.update({
                Index(
                    t,
                    (t.period, Index.Range()),
                    (t.product, Index.Range()),
                    (t.lot, Index.Range()),
                    include=[t.internal_quantity]),
                Index(
                    t,
                    (t.location, Index.Range())),
                })


class Inventory(metaclass=PoolMeta):
    __name__ = 'stock.inventory'

    @classmethod
    def grouping(cls):
        return super().grouping() + ('lot', )


class InventoryLine(metaclass=PoolMeta):
    __name__ = 'stock.inventory.line'
    lot = fields.Many2One('stock.lot', 'Lot',
        domain=[
            ('product', '=', Eval('product', -1)),
            ],
        states={
            'readonly': Eval('inventory_state') != 'draft',
            })

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(1, ('lot', 'ASC'))

    def get_rec_name(self, name):
        rec_name = super().get_rec_name(name)
        if self.lot:
            rec_name += ' - %s' % self.lot.rec_name
        return rec_name

    def get_move(self):
        move = super().get_move()
        if move:
            move.lot = self.lot
        return move


class InventoryCount(metaclass=PoolMeta):
    __name__ = 'stock.inventory.count'

    def default_quantity(self, fields):
        pool = Pool()
        Product = pool.get('product.product')
        InventoryLine = pool.get('stock.inventory.line')
        inventory = self.record
        if isinstance(self.search.search, Product):
            product = self.search.search
            if product.lot_is_required(
                    inventory.location, inventory.location.lost_found_used):
                raise RequiredValidationError(
                    gettext('stock_lot.msg_only_lot',
                        product=product.rec_name))
        values = super().default_quantity(fields)
        line = InventoryLine(values['line'])
        values['lot'] = line.lot.id if line.lot else None
        return values

    def get_line_domain(self, inventory):
        pool = Pool()
        Lot = pool.get('stock.lot')
        domain = super().get_line_domain(inventory)
        if isinstance(self.search.search, Lot):
            domain.append(('lot', '=', self.search.search.id))
        return domain

    def get_line(self):
        pool = Pool()
        Lot = pool.get('stock.lot')

        line = super().get_line()
        if isinstance(self.search.search, Lot):
            lot = self.search.search
            line.product = lot.product
            line.lot = lot
        return line


class InventoryCountSearch(metaclass=PoolMeta):
    __name__ = 'stock.inventory.count.search'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.search.selection.append(('stock.lot', "Lot"))


class InventoryCountQuantity(ModelView):
    __name__ = 'stock.inventory.count.quantity'

    lot = fields.Many2One('stock.lot', "Lot", readonly=True,
        states={
            'invisible': ~Eval('lot', None),
            })
