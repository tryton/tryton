# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, ModelView, Unique, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If


class ProductLocationPlace(ModelSQL, ModelView):
    "Product Location Place"
    __name__ = 'stock.product.location.place'
    _rec_name = 'place'

    template = fields.Many2One(
        'product.template', "Product",
        required=True, ondelete='CASCADE',
        domain=[
            If(Eval('product'),
                ('products', '=', Eval('product', -1)),
                ()),
            ])
    product = fields.Many2One(
        'product.product', "Variant", ondelete='CASCADE',
        domain=[
            If(Eval('template'),
                ('template', '=', Eval('template', -1)),
                ()),
            ])
    location = fields.Many2One(
        'stock.location', "Storage Location",
        required=True, ondelete='CASCADE',
        domain=[
            ('type', '=', 'storage'),
            ])
    place = fields.Char(
        "Place", required=True,
        help="The place where the product is always stored in the location.")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('template_product_location_unique',
                Unique(t, t.template, t.product, t.location),
                'stock_product_location_place.'
                'msg_stock_product_location_unique'),
            ]

    @fields.depends('product', '_parent_product.template')
    def on_change_product(self):
        if self.product:
            self.template = self.product.template

    @classmethod
    def default_location(cls):
        pool = Pool()
        Location = pool.get('stock.location')
        warehouse = Location.get_default_warehouse()
        if warehouse:
            warehouse = Location(warehouse)
            if (warehouse.storage_location
                    and warehouse.storage_location.type == 'storage'):
                return warehouse.storage_location.id
            elif (warehouse.picking_location
                    and warehouse.picking_location.type == 'storage'):
                return warehouse.picking_location.id


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    from_place = fields.Many2One(
        'stock.product.location.place', "From Place", readonly=True,
        domain=[
            If(~Eval('state').in_(['done', 'cancelled']),
                ['OR',
                    ('template.products', '=', Eval('product', -1)),
                    ('product', '=', Eval('product', -1)),
                    ],
                ('location', '=', Eval('from_location', -1)),
                ),
            ])
    to_place = fields.Many2One(
        'stock.product.location.place', "To Place", readonly=True,
        domain=[
            If(~Eval('state').in_(['done', 'cancelled']),
                ['OR',
                    ('template.products', '=', Eval('product', -1)),
                    ('product', '=', Eval('product', -1)),
                    ],
                ('location', '=', Eval('to_location', -1)),
                ),
            ])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._allow_modify_closed_period |= {'from_place', 'to_place'}

    @fields.depends('from_location', 'product')
    def on_change_with_from_place(self):
        if self.product and self.from_location:
            return self.product.get_place(self.from_location)

    @fields.depends('to_location', 'product')
    def on_change_with_to_place(self):
        if self.product and self.to_location:
            return self.product.get_place(self.to_location)

    @fields.depends('from_place')
    def on_change_with_from_location_name(self, name=None):
        name = super().on_change_with_from_location_name(name=name)
        if self.from_place:
            name = ' @ '.join(
                filter(None, [name, self.from_place.rec_name])).strip()
        return name

    @fields.depends('to_place')
    def on_change_with_to_location_name(self, name=None):
        name = super().on_change_with_to_location_name(name=name)
        if self.to_place:
            name = ' @ '.join(
                filter(None, [name, self.to_place.rec_name])).strip()
        return name

    @classmethod
    def create(cls, vlist):
        moves = super().create(vlist)
        cls._sync_places(moves)
        return moves

    @classmethod
    def write(cls, *args):
        # clean places as they maybe no more valid
        actions = iter(args)
        args = []
        for moves, values in zip(actions, actions):
            if {'product', 'from_location', 'to_location'} & values.keys():
                values = values.copy()
                values.setdefault('from_place')
                values.setdefault('to_place')
            args.extend((moves, values))

        super().write(*args)
        moves = sum(args[0:None:2], [])
        cls._sync_places(moves)

    @classmethod
    def _sync_places(cls, moves):
        for move in moves:
            if move.state in {'done', 'cancelled'}:
                continue
            from_place = move.on_change_with_from_place()
            to_place = move.on_change_with_to_place()
            if (move.from_place != from_place
                    or move.to_place != to_place):
                move.from_place = from_place
                move.to_place = to_place
        cls.save(moves)


class ShipmentIn(metaclass=PoolMeta):
    __name__ = 'stock.shipment.in'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        i = cls.inventory_moves.order.index(('to_location', 'ASC'))
        cls.inventory_moves.order.insert(i + 1, ('to_place', 'ASC'))


class ShipmentInReturn(metaclass=PoolMeta):
    __name__ = 'stock.shipment.in.return'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        i = cls.moves.order.index(('from_location', 'ASC'))
        cls.moves.order.insert(i + 1, ('from_place', 'ASC'))


class ShipmentOut(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        i = cls.inventory_moves.order.index(('from_location', 'ASC'))
        cls.inventory_moves.order.insert(i + 1, ('from_place', 'ASC'))


class ShipmentOutReturn(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.return'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        i = cls.inventory_moves.order.index(('to_location', 'ASC'))
        cls.inventory_moves.order.insert(i + 1, ('to_place', 'ASC'))


class ShipmentInternal(metaclass=PoolMeta):
    __name__ = 'stock.shipment.internal'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        i = cls.moves.order.index(('from_location', 'ASC'))
        cls.moves.order.insert(i + 1, ('from_place', 'ASC'))

        i = cls.outgoing_moves.order.index(('from_location', 'ASC'))
        cls.outgoing_moves.order.insert(i + 1, ('from_place', 'ASC'))

        i = cls.incoming_moves.order.index(('to_location', 'ASC'))
        cls.incoming_moves.order.insert(i + 1, ('to_place', 'ASC'))
