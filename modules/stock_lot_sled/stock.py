# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from sql import Union, Join, Select, Table, Null
from sql.conditionals import Greatest

from trytond.pool import PoolMeta, Pool
from trytond.model import ModelView, Workflow, fields
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.tools import grouped_slice

__all__ = ['Configuration', 'Lot', 'Move', 'Period']

DATE_STATE = [
    ('none', 'None'),
    ('optional', 'Optional'),
    ('required', 'Required'),
    ]


class Configuration:
    __metaclass__ = PoolMeta
    __name__ = 'stock.configuration'

    shelf_life_delay = fields.Property(fields.Integer('Shelf Life Delay',
            help='The delay in number of days before '
            'removal from the forecast'))


class Lot:
    __metaclass__ = PoolMeta
    __name__ = 'stock.lot'

    shelf_life_expiration_date = fields.Date('Shelf Life Expiration Date',
        states={
            'required': (
                Eval('shelf_life_expiration_state', 'none') == 'required'),
            'invisible': Eval('shelf_life_expiration_state', 'none') == 'none',
            },
        depends=['shelf_life_expiration_state'])
    shelf_life_expiration_state = fields.Function(
        fields.Selection(DATE_STATE, 'Shelf Life Expiration State'),
        'on_change_with_shelf_life_expiration_state')
    expiration_date = fields.Date('Expiration Date',
        states={
            'required': Eval('expiration_state', 'none') == 'required',
            'invisible': Eval('expiration_state', 'none') == 'none',
            },
        depends=['expiration_state'])
    expiration_state = fields.Function(
        fields.Selection(DATE_STATE, 'Expiration State'),
        'on_change_with_expiration_state')

    @classmethod
    def __setup__(cls):
        super(Lot, cls).__setup__()
        cls._error_messages.update({
                'period_closed_expiration_dates': ('You can not modify '
                    'the expiration dates of lot "%(lot)s" because '
                    'it is used on a move "%(move)s" in a closed period'),
                })

    @fields.depends('product')
    def on_change_with_shelf_life_expiration_state(self, name=None):
        if self.product:
            return self.product.shelf_life_state
        return 'none'

    @fields.depends('product')
    def on_change_with_expiration_state(self, name=None):
        if self.product:
            return self.product.expiration_state
        return 'none'

    @fields.depends('product')
    def on_change_product(self):
        pool = Pool()
        Date = pool.get('ir.date')
        try:
            super(Lot, self).on_change_product()
        except AttributeError:
            pass
        if self.product:
            today = Date.today()
            if (self.product.shelf_life_state != 'none'
                    and self.product.shelf_life_time):
                self.shelf_life_expiration_date = (today
                    + datetime.timedelta(days=self.product.shelf_life_time))
            if (self.product.expiration_state != 'none'
                    and self.product.expiration_time):
                self.expiration_date = (today
                    + datetime.timedelta(days=self.product.expiration_time))

    @classmethod
    def write(cls, *args):
        super(Lot, cls).write(*args)

        actions = iter(args)
        for lots, values in zip(actions, actions):
            if any(f in ['shelf_life_expiration_date', 'expiration_date']
                    for f in values):
                cls.check_sled_period_closed(lots)

    @classmethod
    def check_sled_period_closed(cls, lots):
        Period = Pool().get('stock.period')
        Move = Pool().get('stock.move')
        periods = Period.search([
                ('state', '=', 'closed'),
                ], order=[('date', 'DESC')], limit=1)
        if not periods:
            return
        period, = periods
        for lots in grouped_slice(lots):
            lot_ids = [l.id for l in lots]
            moves = Move.search([
                    ('lot', 'in', lot_ids),
                    ['OR', [
                            ('effective_date', '=', None),
                            ('planned_date', '<=', period.date),
                            ],
                        ('effective_date', '<=', period.date),
                        ]], limit=1)
            if moves:
                move, = moves
                cls.raise_user_error('period_closed_expiration_dates', {
                        'lot': move.lot.rec_name,
                        'move': move.rec_name,
                        })


class Move:
    __metaclass__ = PoolMeta
    __name__ = 'stock.move'

    @classmethod
    def __setup__(cls):
        super(Move, cls).__setup__()
        cls._error_messages.update({
                'expiration_dates': ('The lot "%(lot)s" '
                    'on move "%(move)s" is expired'),
                })

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def do(cls, moves):
        super(Move, cls).do(moves)
        cls.check_expiration_dates(moves)

    @classmethod
    def check_expiration_dates_types(cls):
        "Location types to check for expiration dates"
        return ['supplier', 'customer', 'production']

    @classmethod
    def check_expiration_dates_locations(cls):
        pool = Pool()
        Location = pool.get('stock.location')
        # Prevent pack expired products
        warehouses = Location.search([
                ('type', '=', 'warehouse'),
                ])
        return [w.output_location for w in warehouses]

    @property
    def to_check_expiration(self):
        if (self.lot
                and self.lot.shelf_life_expiration_date
                and self.effective_date > self.lot.shelf_life_expiration_date):
            return True
        return False

    @classmethod
    def check_expiration_dates(cls, moves):
        pool = Pool()
        Group = pool.get('res.group')
        User = pool.get('res.user')
        ModelData = pool.get('ir.model.data')

        types = cls.check_expiration_dates_types()
        locations = cls.check_expiration_dates_locations()

        def in_group():
            group = Group(ModelData.get_id('stock_lot_sled',
                    'group_stock_force_expiration'))
            transition = Transaction()
            user_id = transition.user
            if user_id == 0:
                user_id = transition.context.get('user', user_id)
            if user_id == 0:
                return True
            user = User(user_id)
            return group in user.groups

        for move in moves:
            if not move.to_check_expiration:
                continue
            if (move.from_location.type in types
                    or move.to_location.type in types
                    or move.from_location in locations
                    or move.to_location in locations):
                values = {
                    'move': move.rec_name,
                    'lot': move.lot.rec_name if move.lot else '',
                    }
                if not in_group():
                    cls.raise_user_error('expiration_dates', values)
                else:
                    cls.raise_user_warning('%s.check_expiration_dates' % move,
                        'expiration_dates', values)

    @classmethod
    def compute_quantities_query(cls, location_ids, with_childs=False,
            grouping=('product',), grouping_filter=None):
        pool = Pool()
        Date = pool.get('ir.date')
        Lot = pool.get('stock.lot')
        Config = pool.get('stock.configuration')

        query = super(Move, cls).compute_quantities_query(
            location_ids, with_childs=with_childs, grouping=grouping,
            grouping_filter=grouping_filter)

        context = Transaction().context
        today = Date.today()

        stock_date_end = context.get('stock_date_end') or datetime.date.max
        if query and ((stock_date_end == today and context.get('forecast'))
                or stock_date_end > today):
            lot = Lot.__table__()

            config = Config(1)
            if config.shelf_life_delay:
                expiration_date = stock_date_end + datetime.timedelta(
                    days=config.shelf_life_delay)
            else:
                expiration_date = stock_date_end

            def join(move):
                return move.join(lot, 'LEFT',
                    condition=move.lot == lot.id)

            def find_table(join):
                if not isinstance(join, Join):
                    return
                for pos in ['left', 'right']:
                    item = getattr(join, pos)
                    if isinstance(item, Table):
                        if item._name == cls._table:
                            return join, pos, getattr(join, pos)
                    else:
                        return find_table(item)

            def find_queries(query):
                if isinstance(query, Union):
                    for sub_query in query.queries:
                        for q in find_queries(sub_query):
                            yield q
                elif isinstance(query, Select):
                    yield query

            union, = query.from_
            for sub_query in find_queries(union):
                # Find move table
                for i, table in enumerate(sub_query.from_):
                    if isinstance(table, Table) and table._name == cls._table:
                        sub_query.from_[i] = join(table)
                        break
                    found = find_table(table)
                    if found:
                        join_, pos, table = found
                        setattr(join_, pos, join(table))
                        break
                else:
                    # Not query on move table
                    continue
                sub_query.where &= ((lot.shelf_life_expiration_date == Null)
                    | (lot.shelf_life_expiration_date >= expiration_date))
        return query


class Period:
    __metaclass__ = PoolMeta
    __name__ = 'stock.period'

    @classmethod
    def __setup__(cls):
        super(Period, cls).__setup__()
        cls._error_messages.update({
                'close_period_sled': ('You can not close a period '
                    'before the Shelf Live Expiration Date "%(date)s" '
                    'of Lot "%(lot)s"'),
                })

    @classmethod
    @ModelView.button
    def close(cls, periods):
        pool = Pool()
        Move = pool.get('stock.move')
        Lot = pool.get('stock.lot')
        Date = pool.get('ir.date')
        Lang = pool.get('ir.lang')
        cursor = Transaction().connection.cursor()
        move = Move.__table__()
        lot = Lot.__table__()

        super(Period, cls).close(periods)

        # Don't allow to close a period if all products at this date
        # are not yet expired
        recent_date = max(period.date for period in periods)
        today = Date.today()

        query = move.join(lot, 'INNER',
            condition=move.lot == lot.id).select(lot.id,
                where=(Greatest(move.effective_date, move.planned_date)
                    <= recent_date)
                & (lot.shelf_life_expiration_date >= today)
                )
        cursor.execute(*query)
        lot_id = cursor.fetchone()
        if lot_id:
            lot_id, = lot_id
            lot = Lot(lot_id)
            lang, = Lang.search([
                    ('code', '=', Transaction().language),
                    ])
            date = Lang.strftime(
                lot.shelf_life_expiration_date, lang.code, lang.date)
            cls.raise_user_error('close_period_sled', {
                    'date': date,
                    'lot': lot.rec_name,
                    })
