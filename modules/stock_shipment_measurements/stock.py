# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from functools import wraps
from itertools import groupby

from sql import Literal, Null
from sql.aggregate import Sum
from sql.conditionals import Coalesce
from sql.operators import Concat

from trytond.model import Index, ModelSQL, ModelView, Workflow, fields
from trytond.modules.company.model import CompanyValueMixin
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, Id
from trytond.tools import grouped_slice, reduce_ids
from trytond.transaction import Transaction


class Configuration(metaclass=PoolMeta):
    __name__ = 'stock.configuration'

    measurement_weight_uom = fields.MultiValue(
        fields.Many2One(
            'product.uom', "Measurement Weight UoM", required=True,
            domain=[('category', '=', Id('product', 'uom_cat_weight'))],
            help="The default Unit of Measure for weight."))
    measurement_volume_uom = fields.MultiValue(
        fields.Many2One(
            'product.uom', "Measurement Volume UoM", required=True,
            domain=[('category', '=', Id('product', 'uom_cat_volume'))],
            help="The default Unit of Measure for volume."))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {'measurement_weight_uom', 'measurement_volume_uom'}:
            return pool.get('stock.configuration.measurement')
        return super().multivalue_model(field)

    @classmethod
    def default_measurement_weight_uom(cls, **pattern):
        model = cls.multivalue_model('measurement_weight_uom')
        return model.default_measurement_weight_uom()

    @classmethod
    def default_measurement_volume_uom(cls, **pattern):
        model = cls.multivalue_model('measurement_volume_uom')
        return model.default_measurement_volume_uom()


class ConfigurationMeasurement(ModelSQL, CompanyValueMixin):
    "Stock Configuration Measurement"
    __name__ = 'stock.configuration.measurement'

    measurement_weight_uom = fields.Many2One(
        'product.uom', "Measurement Weight UoM", required=True,
        domain=[('category', '=', Id('product', 'uom_cat_weight'))])
    measurement_volume_uom = fields.Many2One(
        'product.uom', "Measurement Volume UoM", required=True,
        domain=[('category', '=', Id('product', 'uom_cat_volume'))])

    @classmethod
    def default_measurement_weight_uom(cls):
        pool = Pool()
        Uom = pool.get('product.uom')
        ModelData = pool.get('ir.model.data')
        return Uom(ModelData.get_id('product', 'uom_kilogram')).id

    @classmethod
    def default_measurement_volume_uom(cls):
        pool = Pool()
        Uom = pool.get('product.uom')
        ModelData = pool.get('ir.model.data')
        return Uom(ModelData.get_id('product', 'uom_liter')).id


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    internal_weight = fields.Float(
        "Internal Weight", readonly=True,
        help="The weight of the moved product in kg.")
    internal_volume = fields.Float(
        "Internal Volume", readonly=True,
        help="The volume of the moved product in liter.")

    @classmethod
    def _get_internal_weight(cls, quantity, unit, product):
        pool = Pool()
        Uom = pool.get('product.uom')
        ModelData = pool.get('ir.model.data')

        kg = Uom(ModelData.get_id('product', 'uom_kilogram'))

        # Use first the weight from product_measurements
        # as it could include some handling weight
        if product.weight is not None:
            internal_quantity = cls._get_internal_quantity(
                quantity, unit, product)
            return Uom.compute_qty(
                product.weight_uom, internal_quantity * product.weight, kg,
                round=False)
        elif unit.category == kg.category:
            return Uom.compute_qty(unit, quantity, kg, round=False)
        else:
            return None

    @classmethod
    def _get_internal_volume(cls, quantity, unit, product):
        pool = Pool()
        Uom = pool.get('product.uom')
        ModelData = pool.get('ir.model.data')

        liter = Uom(ModelData.get_id('product', 'uom_liter'))

        # Use first the volume from product_measurements
        # as it could include some handling volume
        if product.volume is not None:
            internal_quantity = cls._get_internal_quantity(
                quantity, unit, product)
            return Uom.compute_qty(
                product.volume_uom, internal_quantity * product.volume, liter,
                round=False)
        elif unit.category == liter.category:
            return Uom.compute_qty(unit, quantity, liter, round=False)
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
            unit = Uom(values['unit'])
            quantity = values['quantity']
            internal_weight = cls._get_internal_weight(quantity, unit, product)
            if internal_weight is not None:
                values['internal_weight'] = internal_weight
            internal_volume = cls._get_internal_volume(quantity, unit, product)
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
                    move.quantity, move.unit, move.product)
                if (internal_weight is not None
                        and internal_weight != move.internal_weight
                        and internal_weight != values.get('internal_weight')):
                    write['internal_weight'] = internal_weight
                internal_volume = cls._get_internal_volume(
                    move.quantity, move.unit, move.product)
                if (internal_volume is not None
                        and internal_volume != move.internal_volume
                        and internal_volume != values.get('internal_volume')):
                    write['internal_volume'] = internal_volume
                if write:
                    to_write.extend(([move], write))
        if to_write:
            cls.write(*to_write)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, moves):
        super().cancel(moves)
        shipments = defaultdict(set)
        for move in moves:
            if isinstance(move.shipment, MeasurementsMixin):
                shipments[move.shipment.__class__].add(move.shipment)
        for Shipment, shipments in shipments.items():
            Shipment.set_measurements(list(shipments))


class MeasurementsMixin(object):
    __slots__ = ()
    weight = fields.Function(
        fields.Float(
            "Weight", digits='weight_uom',
            states={
                'invisible': ~Eval('weight'),
                },
            help="The total weight of the record's moves."),
        'get_measurements', searcher='search_measurements')
    internal_weight = fields.Float("Internal Weight", readonly=True)
    weight_uom = fields.Function(
        fields.Many2One(
            'product.uom', "Weight UoM",
            help="The Unit of Measure of weight."),
        'get_measurements_uom')
    volume = fields.Function(
        fields.Float(
            "Volume", digits='volume_uom',
            states={
                'invisible': ~Eval('volume'),
                },
            help="The total volume of the record's moves."),
        'get_measurements', searcher='search_measurements')
    internal_volume = fields.Float("Internal Volume", readonly=True)
    volume_uom = fields.Function(
        fields.Many2One(
            'product.uom', "Volume UoM",
            help="The Unit of Measure of volume."),
        'get_measurements_uom')

    @classmethod
    def __setup__(cls):
        super().__setup__()

        t = cls.__table__()
        states = cls._measurements_states()
        if states:
            cls._sql_indexes.update({
                    Index(
                        t,
                        (t.id, Index.Range()),
                        where=(~t.state.in_(states)
                            | (t.internal_weight == Null)
                            | (t.internal_volume == Null))),
                    Index(t,
                        (t.internal_weight, Index.Range()),
                        where=(t.state.in_(states)
                            & (t.internal_weight != Null)
                            & (t.internal_volume != Null))),
                    Index(t,
                        (t.internal_volume, Index.Range()),
                        where=(t.state.in_(states)
                            & (t.internal_weight != Null)
                            & (t.internal_volume != Null))),
                    })

    @classmethod
    def __register__(cls, module):
        table_h = cls.__table_handler__(module)
        set_measurements = (
            not table_h.column_exist('internal_weight')
            or not table_h.column_exist('internal_volume'))

        super().__register__(module)

        if set_measurements:
            cls.set_measurements()

    @classmethod
    def _measurements_states(cls):
        return []

    @classmethod
    def get_measurements_uom(cls, shipments, name):
        pool = Pool()
        Configuration = pool.get('stock.configuration')
        configuration = Configuration(1)
        uoms = {}
        for company, shipments in groupby(shipments, key=lambda s: s.company):
            uom = configuration.get_multivalue(
                'measurement_%s' % name, company=company.id)
            for shipment in shipments:
                uoms[shipment.id] = uom.id
        return uoms

    @classmethod
    def set_measurements(cls, shipments=None):
        pool = Pool()
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')

        cursor = Transaction().connection.cursor()
        table = cls.__table__()
        move = Move.__table__()
        location = Location.__table__()

        if not (states := cls._measurements_states()):
            return

        query = (table.update(
                [table.internal_weight, table.internal_volume],
                [move
                    .join(location,
                        condition=cls._measurements_location_condition(
                            table, move, location))
                    .select(
                        Sum(Coalesce(move.internal_weight, 0)),
                        where=cls._measurements_move_condition(table, move)
                        & (move.state != 'cancelled')),
                    move
                    .join(location,
                        condition=cls._measurements_location_condition(
                            table, move, location))
                    .select(
                        Sum(Coalesce(move.internal_volume, 0)),
                        where=cls._measurements_move_condition(table, move)
                        & (move.state != 'cancelled'))],
                where=table.state.in_(states)))

        if shipments:
            where = query.where
            for sub_shipments in grouped_slice(shipments):
                query.where = (
                    where & reduce_ids(table.id, map(int, sub_shipments)))
                cursor.execute(*query)
        else:
            cursor.execute(*query)

        if shipments:
            cls.write(shipments, {})

    @classmethod
    def get_measurements(cls, shipments, names):
        pool = Pool()
        Location = pool.get('stock.location')
        ModelData = pool.get('ir.model.data')
        Move = pool.get('stock.move')
        Uom = pool.get('product.uom')

        kg = Uom(ModelData.get_id('product', 'uom_kilogram'))
        liter = Uom(ModelData.get_id('product', 'uom_liter'))

        cursor = Transaction().connection.cursor()
        table = cls.__table__()
        move = Move.__table__()
        location = Location.__table__()
        measurements = defaultdict(lambda: defaultdict(lambda: None))

        query = table.join(
            move, type_='LEFT',
            condition=cls._measurements_move_condition(table, move)
            & (move.state != 'cancelled')
            ).join(
                location,
                condition=cls._measurements_location_condition(
                    table, move, location)
                ).select(
                    table.id,
                    Sum(Coalesce(move.internal_weight, 0)),
                    Sum(Coalesce(move.internal_volume, 0)),
                    group_by=[table.id])

        weights, volumes = {}, {}
        states = cls._measurements_states()
        for sub_shipments in grouped_slice(
                (s for s in shipments
                    if s.state not in states
                    or s.internal_weight is None
                    or s.internal_volume is None)):
            query.where = reduce_ids(
                table.id, [s.id for s in sub_shipments])
            cursor.execute(*query)
            for id_, weight, volume in cursor:
                weights[id_] = weight
                volumes[id_] = volume

        for shipment in shipments:
            if 'weight' in names:
                weight = weights.get(
                    shipment.id, shipment.internal_weight)
                measurements['weight'][shipment.id] = Uom.compute_qty(
                    kg, weight, shipment.weight_uom)
            if 'volume' in names:
                volume = volumes.get(
                    shipment.id, shipment.internal_volume)
                measurements['volume'][shipment.id] = Uom.compute_qty(
                    liter, volume, shipment.volume_uom)
        return measurements

    @classmethod
    def search_measurements(cls, name, clause):
        pool = Pool()
        Configuration = pool.get('stock.configuration')
        Location = pool.get('stock.location')
        ModelData = pool.get('ir.model.data')
        Move = pool.get('stock.move')
        Uom = pool.get('product.uom')

        table = cls.__table__()
        move = Move.__table__()
        location = Location.__table__()
        configuration = Configuration(1)
        uom = configuration.get_multivalue('measurement_%s_uom' % name)

        _, operator, value = clause

        Operator = fields.SQL_OPERATORS[operator]
        if name == 'weight':
            measurement = Sum(Coalesce(move.internal_weight, 0))
            column = table.internal_weight
            if value is not None:
                kg = Uom(ModelData.get_id('product', 'uom_kilogram'))
                if isinstance(value, (int, float)):
                    value = Uom.compute_qty(uom, value, kg, round=False)
                else:
                    value = [
                        Uom.compute_qty(uom, v, kg, round=False)
                        if v is not None else v
                        for v in value]
        else:
            measurement = Sum(Coalesce(move.internal_volume, 0))
            column = table.internal_volume
            if value is not None:
                liter = Uom(ModelData.get_id('product', 'uom_liter'))
                if isinstance(value, (int, float)):
                    value = Uom.compute_qty(uom, value, liter, round=False)
                else:
                    value = [
                        Uom.compute_qty(uom, v, liter, round=False)
                        if v is not None else v
                        for v in value]

        if states := cls._measurements_states():
            state_clause = table.state.in_(states)
        else:
            state_clause = Literal(False)

        query = table.join(
            move, type_='LEFT',
            condition=cls._measurements_move_condition(table, move)
            & (move.state != 'cancelled')
            ).join(
                location,
                condition=cls._measurements_location_condition(
                    table, move, location)
                ).select(
                    table.id,
                    where=~state_clause
                    | (table.internal_weight == Null)
                    | (table.internal_volume == Null),
                    group_by=[table.id],
                    having=Operator(measurement, value))
        query |= table.select(
            table.id,
            where=state_clause
            & (table.internal_weight != Null)
            & (table.internal_volume != Null)
            & Operator(column, value))
        return [('id', 'in', query)]

    @classmethod
    def _measurements_move_condition(cls, table, move):
        return Concat(cls.__name__ + ',', table.id) == move.shipment

    @classmethod
    def _measurements_location_condition(cls, table, move, location):
        raise NotImplementedError


def set_measurements(func):
    @wraps(func)
    def wrapper(cls, shipments, *args, **kwargs):
        result = func(cls, shipments, *args, **kwargs)
        cls.set_measurements(shipments)
        return result
    return wrapper


class ShipmentIn(MeasurementsMixin, object, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in'

    @classmethod
    def _measurements_states(cls):
        return super()._measurements_states() + ['done', 'cancelled']

    @classmethod
    def _measurements_location_condition(cls, shipment, move, location):
        return (
            (move.from_location == location.id)
            & (location.type == 'supplier'))

    @classmethod
    @ModelView.button
    @set_measurements
    @Workflow.transition('done')
    def do(cls, shipments):
        super().do(shipments)

    @classmethod
    @ModelView.button
    @set_measurements
    @Workflow.transition('cancelled')
    def cancel(cls, shipments):
        super().cancel(shipments)


class ShipmentInReturn(MeasurementsMixin, object, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in.return'

    @classmethod
    def _measurements_states(cls):
        return super()._measurements_states() + ['done', 'cancelled']

    @classmethod
    def _measurements_location_condition(cls, shipment, move, location):
        return move.from_location == location.id

    @classmethod
    @ModelView.button
    @set_measurements
    @Workflow.transition('done')
    def do(cls, shipments):
        super().do(shipments)

    @classmethod
    @ModelView.button
    @set_measurements
    @Workflow.transition('cancelled')
    def cancel(cls, shipments):
        super().cancel(shipments)


class ShipmentOut(MeasurementsMixin, object, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    @classmethod
    def _measurements_states(cls):
        return super()._measurements_states() + ['done', 'cancelled']

    @classmethod
    def _measurements_location_condition(cls, shipment, move, location):
        return (
            (move.to_location == location.id)
            & (location.type == 'customer'))

    @fields.depends('carrier')
    def _parcel_weight(self, parcel):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        Uom = pool.get('product.uom')
        kg = Uom(ModelData.get_id('product', 'uom_kilogram'))
        weight = super()._parcel_weight(parcel)
        if self.carrier:
            carrier_uom = self.carrier.weight_uom
            packages = {p for l in parcel for p in l.package_path}
            for package in packages:
                if package.additional_weight:
                    weight += Uom.compute_qty(
                        kg, package.additional_weight, carrier_uom,
                        round=False)
        return weight

    @classmethod
    @ModelView.button
    @set_measurements
    @Workflow.transition('done')
    def do(cls, shipments):
        super().do(shipments)

    @classmethod
    @ModelView.button
    @set_measurements
    @Workflow.transition('cancelled')
    def cancel(cls, shipments):
        super().cancel(shipments)


class ShipmentOutReturn(MeasurementsMixin, object, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.return'

    @classmethod
    def _measurements_states(cls):
        return super()._measurements_states() + ['done', 'cancelled']

    @classmethod
    def _measurements_location_condition(cls, shipment, move, location):
        return (
            (move.from_location == location.id)
            & (location.type == 'customer'))

    @classmethod
    @ModelView.button
    @set_measurements
    @Workflow.transition('done')
    def do(cls, shipments):
        super().do(shipments)

    @classmethod
    @ModelView.button
    @set_measurements
    @Workflow.transition('cancelled')
    def cancel(cls, shipments):
        super().cancel(shipments)

# TODO ShipmentInternal


class Package(MeasurementsMixin, object, metaclass=PoolMeta):
    __name__ = 'stock.package'

    additional_weight = fields.Float(
        "Additional Weight", digits='additional_weight_uom',
        help="The weight to add to the packages.")
    additional_weight_uom = fields.Many2One(
        'product.uom', "Additional Weight UoM",
        domain=[('category', '=', Id('product', 'uom_cat_weight'))],
        states={
            'required': Bool(Eval('additional_weight')),
            },
        help="The Unit of Measure for additional weight.")
    total_weight = fields.Function(
        fields.Float(
            "Total Weight", digits='weight_uom',
            states={
                'invisible': ~Eval('total_weight'),
                },
            help="The total weight of the packages."),
        'get_total_measurements')
    total_volume = fields.Function(
        fields.Float(
            "Total Volume", digits='volume_uom',
            states={
                'invisible': ~Eval('total_volume'),
                },
            help="The total volume of the packages."),
        'get_total_measurements')

    @classmethod
    def default_additional_weight_uom(cls):
        pool = Pool()
        Configuration = pool.get('stock.configuration')
        configuration = Configuration(1)
        return configuration.get_multivalue('measurement_weight_uom').id

    @classmethod
    def _measurements_move_condition(cls, package, move):
        return package.id == move.package

    @classmethod
    def _measurements_location_condition(cls, package, move, location):
        return move.to_location == location.id

    def get_total_measurements(self, name, round=True):
        pool = Pool()
        Uom = pool.get('product.uom')
        field = name[len('total_'):]

        if name == 'total_volume' and self.packaging_volume is not None:
            return Uom.compute_qty(
                self.packaging_volume_uom, self.packaging_volume,
                self.volume_uom, round=round)

        measurement = (
            (getattr(self, field) or 0)
            + sum(p.get_total_measurements(name, round=False)
                for p in self.children))
        if name == 'total_weight':
            if self.additional_weight:
                measurement += Uom.compute_qty(
                    self.additional_weight_uom, self.additional_weight,
                    self.weight_uom, round=False)
            if self.packaging_weight:
                measurement += Uom.compute_qty(
                    self.packaging_weight_uom, self.packaging_weight,
                    self.weight_uom, round=False)
        if round:
            return getattr(self, field + '_uom').round(measurement)
        else:
            return measurement


class MeasurementsPackageMixin:
    __slots__ = ()

    packages_weight = fields.Function(
        fields.Float("Packages Weight", digits='weight_uom',
            help="The total weight of the packages."),
        'get_packages_measurements')
    packages_volume = fields.Function(
        fields.Float("Packages Volume", digits='volume_uom',
            help="The total volume of the packages."),
        'get_packages_measurements')

    def get_packages_measurements(self, name):
        name = name[len('packages_'):]
        uom = getattr(self, name + '_uom')
        return uom.round(
            sum(getattr(p, 'total_' + name)for p in self.root_packages))


class ShipmentOutPackage(MeasurementsPackageMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'


class ShipmentInReturnPackage(MeasurementsPackageMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in.return'
