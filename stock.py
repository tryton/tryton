# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from functools import wraps

from trytond.i18n import gettext
from trytond.model import ModelView, ModelSQL, fields
from trytond.model.exceptions import AccessError, RequiredValidationError
from trytond.pyson import Eval
from trytond.pool import Pool, PoolMeta
from trytond.tools import grouped_slice
from trytond.transaction import Transaction
from trytond.modules.stock import StockMixin


def check_no_move(func):
    def find_moves(cls, records, state=None):
        pool = Pool()
        Move = pool.get('stock.move')
        for sub_records in grouped_slice(records):
            domain = [
                ('lot', 'in', [r.id for r in sub_records])
                ]
            if state:
                domain.append(('state', '=', state))
            moves = Move.search(domain, limit=1, order=[])
            if moves:
                return True
        return False

    @wraps(func)
    def decorator(cls, *args):
        transaction = Transaction()
        if (transaction.user != 0
                and transaction.context.get('_check_access')):
            actions = iter(args)
            for records, values in zip(actions, actions):
                for field, state, error in cls._modify_no_move:
                    if field in values:
                        if find_moves(cls, records, state):
                            raise AccessError(gettext(error))
                        # No moves for those records
                        break
        func(cls, *args)
    return decorator


class Lot(ModelSQL, ModelView, StockMixin):
    "Stock Lot"
    __name__ = 'stock.lot'
    _rec_name = 'number'
    number = fields.Char('Number', required=True, select=True)
    product = fields.Many2One('product.product', 'Product', required=True)
    quantity = fields.Function(fields.Float('Quantity'), 'get_quantity',
        searcher='search_quantity')
    forecast_quantity = fields.Function(fields.Float('Forecast Quantity'),
        'get_quantity', searcher='search_quantity')

    @classmethod
    def __setup__(cls):
        super(Lot, cls).__setup__()
        cls._modify_no_move = [
            ('product', None, 'stock_lot.msg_change_product'),
            ]

    @classmethod
    def get_quantity(cls, lots, name):
        location_ids = Transaction().context.get('locations')
        product_ids = list(set(l.product.id for l in lots))
        return cls._get_quantity(lots, name, location_ids,
            grouping=('product', 'lot',), grouping_filter=(product_ids,))

    @classmethod
    def search_quantity(cls, name, domain=None):
        location_ids = Transaction().context.get('locations')
        return cls._search_quantity(name, location_ids, domain,
            grouping=('product', 'lot'))

    @classmethod
    @check_no_move
    def write(cls, *args):
        super(Lot, cls).write(*args)


class LotByLocationContext(ModelView):
    'Lot by Location'
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


class LotByWarehouseContext(LotByLocationContext):
    "Lot by Warehouse"
    __name__ = 'stock.lots_by_warehouse.context'
    warehouse = fields.Many2One(
        'stock.location', "Warehouse", required=True,
        domain=[
            ('type', '=', 'warehouse'),
            ],
        )
    locations = fields.Function(
        fields.Many2Many('stock.location', None, None, "Locations"),
        'on_change_with_locations')

    @classmethod
    def default_warehouse(cls):
        return Pool().get('stock.location').get_default_warehouse()

    @fields.depends('warehouse')
    def on_change_with_locations(self, name=None):
        locations = []
        if self.warehouse:
            locations.append(self.warehouse.id)
        return locations


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
    lot = fields.Many2One('stock.lot', 'Lot',
        domain=[
            ('product', '=', Eval('product')),
            ],
        states={
            'readonly': Eval('state').in_(['cancelled', 'done']),
            },
        depends=['state', 'product'])

    def check_lot(self):
        "Check if lot is required"
        if (self.state == 'done'
                and self.internal_quantity
                and not self.lot
                and self.product.lot_is_required(
                    self.from_location, self.to_location)):
            raise RequiredValidationError(
                gettext('stock_lot.msg_lot_required',
                    product=self.product.rec_name))

    @classmethod
    def validate(cls, moves):
        super(Move, cls).validate(moves)
        for move in moves:
            move.check_lot()


class ShipmentIn(metaclass=PoolMeta):
    __name__ = 'stock.shipment.in'

    def _get_inventory_move(self, incoming_move):
        move = super()._get_inventory_move(incoming_move)
        if move and incoming_move.lot:
            move.lot = incoming_move.lot
        return move


class ShipmentOut(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    def _get_inventory_move(self, outgoing_move):
        move = super()._get_inventory_move(outgoing_move)
        if move and outgoing_move.lot:
            move.lot = outgoing_move.lot
        return move

    def _sync_move_key(self, move):
        return super()._sync_move_key(move) + (('lot', move.lot),)


class ShipmentOutReturn(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.return'

    def _get_inventory_move(self, incoming_move):
        move = super()._get_inventory_move(incoming_move)
        if move and incoming_move.lot:
            move.lot = incoming_move.lot
        return move


class ShipmentInternal(metaclass=PoolMeta):
    __name__ = 'stock.shipment.internal'

    def _sync_move_key(self, move):
        return super()._sync_move_key(move) + (('lot', move.lot),)


class Period(metaclass=PoolMeta):
    __name__ = 'stock.period'
    lot_caches = fields.One2Many('stock.period.cache.lot', 'period',
        'Lot Caches', readonly=True)

    @classmethod
    def groupings(cls):
        return super(Period, cls).groupings() + [('product', 'lot')]

    @classmethod
    def get_cache(cls, grouping):
        pool = Pool()
        Cache = super(Period, cls).get_cache(grouping)
        if grouping == ('product', 'lot'):
            return pool.get('stock.period.cache.lot')
        return Cache


class PeriodCacheLot(ModelSQL, ModelView):
    '''
    Stock Period Cache per Lot

    It is used to store cached computation of stock quantities per lot.
    '''
    __name__ = 'stock.period.cache.lot'
    period = fields.Many2One('stock.period', 'Period', required=True,
        readonly=True, select=True, ondelete='CASCADE')
    location = fields.Many2One('stock.location', 'Location', required=True,
        readonly=True, select=True, ondelete='CASCADE')
    product = fields.Many2One('product.product', 'Product', required=True,
        readonly=True, ondelete='CASCADE')
    lot = fields.Many2One('stock.lot', 'Lot', readonly=True,
        ondelete='CASCADE')
    internal_quantity = fields.Float('Internal Quantity', readonly=True)


class Inventory(metaclass=PoolMeta):
    __name__ = 'stock.inventory'

    @classmethod
    def grouping(cls):
        return super(Inventory, cls).grouping() + ('lot', )


class InventoryLine(metaclass=PoolMeta):
    __name__ = 'stock.inventory.line'
    lot = fields.Many2One('stock.lot', 'Lot',
        domain=[
            ('product', '=', Eval('product')),
            ],
        states={
            'readonly': Eval('inventory_state') != 'draft',
            },
        depends=['product', 'inventory_state'])

    @classmethod
    def __setup__(cls):
        super(InventoryLine, cls).__setup__()
        cls._order.insert(1, ('lot', 'ASC'))

    def get_rec_name(self, name):
        rec_name = super(InventoryLine, self).get_rec_name(name)
        if self.lot:
            rec_name += ' - %s' % self.lot.rec_name
        return rec_name

    def get_move(self):
        move = super(InventoryLine, self).get_move()
        if move:
            move.lot = self.lot
        return move


class InventoryCount(metaclass=PoolMeta):
    __name__ = 'stock.inventory.count'

    def default_quantity(self, fields):
        pool = Pool()
        Product = pool.get('product.product')
        inventory = self.record
        if isinstance(self.search.search, Product):
            product = self.search.search
            if product.lot_is_required(
                    inventory.location, inventory.location.lost_found_used):
                raise RequiredValidationError(
                    gettext('stock_lot.msg_only_lot',
                        product=product.rec_name))
        return super(InventoryCount, self).default_quantity(fields)

    def get_line_domain(self, inventory):
        pool = Pool()
        Lot = pool.get('stock.lot')
        domain = super(InventoryCount, self).get_line_domain(inventory)
        if isinstance(self.search.search, Lot):
            domain.append(('lot', '=', self.search.search.id))
        return domain

    def get_line_values(self, inventory):
        pool = Pool()
        Lot = pool.get('stock.lot')
        values = super(InventoryCount, self).get_line_values(inventory)
        if isinstance(self.search.search, Lot):
            lot = self.search.search
            values['product'] = lot.product.id
            values['lot'] = lot.id
        return values


class InventoryCountSearch(metaclass=PoolMeta):
    __name__ = 'stock.inventory.count.search'

    @classmethod
    def __setup__(cls):
        super(InventoryCountSearch, cls).__setup__()
        cls.search.selection.append(('stock.lot', "Lot"))
