# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from sql.aggregate import Sum
from sql.operators import Concat

from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.tools import grouped_slice, reduce_ids
from trytond.transaction import Transaction


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    internal_weight = fields.Float(
        "Internal Weight", readonly=True,
        help="The weight of the moved product in kg.")
    internal_volume = fields.Float(
        "Internal Volume", readonly=True,
        help="The volume of the moved product in liter.")

    @classmethod
    def _get_internal_weight(cls, quantity, uom, product):
        pool = Pool()
        Uom = pool.get('product.uom')
        ModelData = pool.get('ir.model.data')

        kg = Uom(ModelData.get_id('product', 'uom_kilogram'))

        # Use first the weight from product_measurements
        # as it could include some handling weight
        if product.weight is not None:
            internal_quantity = cls._get_internal_quantity(
                quantity, uom, product)
            return Uom.compute_qty(
                product.weight_uom, internal_quantity * product.weight, kg,
                round=False)
        elif uom.category == kg.category:
            return Uom.compute_qty(uom, quantity, kg, round=False)
        else:
            return None

    @classmethod
    def _get_internal_volume(cls, quantity, uom, product):
        pool = Pool()
        Uom = pool.get('product.uom')
        ModelData = pool.get('ir.model.data')

        liter = Uom(ModelData.get_id('product', 'uom_liter'))

        # Use first the volume from product_measurements
        # as it could include some handling volume
        if product.volume is not None:
            internal_quantity = cls._get_internal_quantity(
                quantity, uom, product)
            return Uom.compute_qty(
                product.volume_uom, internal_quantity * product.volume, liter,
                round=False)
        elif uom.category == liter.category:
            return Uom.compute_qty(uom, quantity, liter, round=False)
        else:
            return None

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Product = pool.get('product.product')
        Uom = pool.get('product.uom')

        vlist = [v.copy() for v in vlist]
        for values in vlist:
            product = Product(values['product'])
            uom = Uom(values['uom'])
            quantity = values['quantity']
            internal_weight = cls._get_internal_weight(quantity, uom, product)
            if internal_weight is not None:
                values['internal_weight'] = internal_weight
            internal_volume = cls._get_internal_volume(quantity, uom, product)
            if internal_volume is not None:
                values['internal_volume'] = internal_volume
        return super(Move, cls).create(vlist)

    @classmethod
    def write(cls, *args):
        super(Move, cls).write(*args)

        to_write = []
        actions = iter(args)
        for moves, values in zip(actions, actions):
            for move in moves:
                write = {}
                internal_weight = cls._get_internal_weight(
                    move.quantity, move.uom, move.product)
                if (internal_weight is not None
                        and internal_weight != move.internal_weight
                        and internal_weight != values.get('internal_weight')):
                    write['internal_weight'] = internal_weight
                internal_volume = cls._get_internal_volume(
                    move.quantity, move.uom, move.product)
                if (internal_volume is not None
                        and internal_volume != move.internal_volume
                        and internal_volume != values.get('internal_volume')):
                    write['internal_volume'] = internal_volume
                if write:
                    to_write.extend(([move], write))
        if to_write:
            cls.write(*to_write)


class MeasurementsMixin(object):
    __slots__ = ()
    weight = fields.Function(
        fields.Float("Weight", digits=None,
            help="The total weight of the record's moves in kg."),
        'get_measurements', searcher='search_measurements')
    volume = fields.Function(
        fields.Float("Volume", digits=None,
            help="The total volume of the record's moves in liter."),
        'get_measurements', searcher='search_measurements')

    @classmethod
    def get_measurements(cls, shipments, names):
        pool = Pool()
        Move = pool.get('stock.move')
        Location = pool.get('stock.location')

        cursor = Transaction().connection.cursor()
        table = cls.__table__()
        move = Move.__table__()
        location = Location.__table__()
        measurements = defaultdict(lambda: defaultdict(lambda: None))

        query = table.join(
            move, type_='LEFT',
            condition=cls._measurements_move_condition(table, move)
            ).join(
                location,
                condition=cls._measurements_location_condition(
                    table, move, location)
                ).select(
                    table.id,
                    Sum(move.internal_weight),
                    Sum(move.internal_volume),
                    group_by=[table.id])

        for sub_shipments in grouped_slice(shipments):
            query.where = reduce_ids(
                table.id, [s.id for s in sub_shipments])
            cursor.execute(*query)
            for id_, weight, volume in cursor:
                if 'weight' in names:
                    measurements['weight'][id_] = weight
                if 'volume' in names:
                    measurements['volume'][id_] = volume
        return measurements

    @classmethod
    def search_measurements(cls, name, clause):
        pool = Pool()
        Move = pool.get('stock.move')
        Location = pool.get('stock.location')

        table = cls.__table__()
        move = Move.__table__()
        location = Location.__table__()

        _, operator, value = clause

        Operator = fields.SQL_OPERATORS[operator]
        if name == 'weight':
            measurement = Sum(move.internal_weight)
        else:
            measurement = Sum(move.internal_volume)

        query = table.join(
            move, type_='LEFT',
            condition=cls._measurements_move_condition(table, move)
            ).join(
                location,
                condition=cls._measurements_location_condition(
                    table, move, location)
                ).select(
                    table.id,
                    group_by=[table.id],
                    having=Operator(measurement, value))
        return [('id', 'in', query)]

    @classmethod
    def _measurements_move_condition(cls, table, move):
        return Concat(cls.__name__ + ',', table.id) == move.shipment

    @classmethod
    def _measurements_location_condition(cls, table, move, location):
        raise NotImplementedError


class ShipmentIn(MeasurementsMixin, object, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in'

    @classmethod
    def _measurements_location_condition(cls, shipment, move, location):
        return (
            (move.from_location == location.id)
            & (location.type == 'supplier'))


class ShipmentInReturn(MeasurementsMixin, object, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in.return'

    @classmethod
    def _measurements_location_condition(cls, shipment, move, location):
        return move.from_location == location.id


class ShipmentOut(MeasurementsMixin, object, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    @classmethod
    def _measurements_location_condition(cls, shipment, move, location):
        return (
            (move.to_location == location.id)
            & (location.type == 'customer'))


class ShipmentOutReturn(MeasurementsMixin, object, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.return'

    @classmethod
    def _measurements_location_condition(cls, shipment, move, location):
        return (
            (move.from_location == location.id)
            & (location.type == 'customer'))

# TODO ShipmentInternal


class Package(MeasurementsMixin, object, metaclass=PoolMeta):
    __name__ = 'stock.package'

    additional_weight = fields.Float(
        "Additional Weight",
        help="The weight to add to the packages in kg.")
    total_weight = fields.Function(
        fields.Float("Total Weight", digits=None,
            help="The total weight of the packages in kg."),
        'get_total_measurements')
    total_volume = fields.Function(
        fields.Float("Total Volume", digits=None,
            help="The total volume of the packages in liter."),
        'get_total_measurements')

    @classmethod
    def _measurements_move_condition(cls, package, move):
        return package.id == move.package

    @classmethod
    def _measurements_location_condition(cls, package, move, location):
        return move.to_location == location.id

    def get_total_measurements(self, name):
        field = name[len('total_'):]
        measurement = ((getattr(self, field) or 0)
            + sum(p.get_total_measurements(name) for p in self.children))
        if name == 'total_weight' and self.additional_weight:
            measurement += self.additional_weight
        return measurement
