# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql.functions import CharLength

from trytond.i18n import gettext
from trytond.model import (
    DeactivableMixin, ModelSQL, ModelView, Workflow, fields, tree)
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, Id, If
from trytond.transaction import Transaction

from .exceptions import PackageError, PackageValidationError


class Configuration(metaclass=PoolMeta):
    __name__ = 'stock.configuration'
    package_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Package Sequence", required=True,
            domain=[
                ('company', 'in', [
                        Eval('context', {}).get('company', -1), None]),
                ('sequence_type', '=',
                    Id('stock_package', 'sequence_type_package')),
                ]))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'package_sequence':
            return pool.get('stock.configuration.sequence')
        return super().multivalue_model(field)

    @classmethod
    def default_package_sequence(cls, **pattern):
        return cls.multivalue_model(
            'package_sequence').default_package_sequence()


class ConfigurationSequence(metaclass=PoolMeta):
    __name__ = 'stock.configuration.sequence'
    package_sequence = fields.Many2One(
        'ir.sequence', "Package Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('sequence_type', '=',
                Id('stock_package', 'sequence_type_package')),
            ])

    @classmethod
    def default_package_sequence(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id('stock_package', 'sequence_package')
        except KeyError:
            return None


class MeasurementsMixin:
    __slots__ = ()

    length = fields.Float(
        "Length", digits='length_uom',
        help="The length of the package.")
    length_uom = fields.Many2One(
        'product.uom', "Length UoM",
        domain=[('category', '=', Id('product', 'uom_cat_length'))],
        states={
            'required': Bool(Eval('length')),
            },
        help="The Unit of Measure for the package length.")
    height = fields.Float(
        "Height", digits='height_uom',
        help="The height of the package.")
    height_uom = fields.Many2One(
        'product.uom', "Height UoM",
        domain=[('category', '=', Id('product', 'uom_cat_length'))],
        states={
            'required': Bool(Eval('height')),
            },
        help="The Unit of Measure for the package height.")
    width = fields.Float(
        "Width", digits='width_uom',
        help="The width of the package.")
    width_uom = fields.Many2One(
        'product.uom', "Width UoM",
        domain=[('category', '=', Id('product', 'uom_cat_length'))],
        states={
            'required': Bool(Eval('width')),
            },
        help="The Unit of Measure for the package width.")

    packaging_volume = fields.Float(
        "Packaging Volume", digits='packaging_volume_uom',
        states={
            'readonly': (
                Bool(Eval('length'))
                & Bool(Eval('height'))
                & Bool(Eval('width'))),
            },
        help="The volume of the package.")
    packaging_volume_uom = fields.Many2One(
        'product.uom', "Packaging Volume UoM",
        domain=[('category', '=', Id('product', 'uom_cat_volume'))],
        states={
            'required': Bool(Eval('packaging_volume')),
            },
        help="The Unit of Measure for the packaging volume.")

    packaging_weight = fields.Float(
        "Packaging Weight", digits='packaging_weight_uom',
        help="The weight of the package when empty.")
    packaging_weight_uom = fields.Many2One(
        'product.uom', "Packaging Weight UoM",
        domain=[('category', '=', Id('product', 'uom_cat_weight'))],
        states={
            'required': Bool(Eval('packaging_weight')),
            },
        help="The Unit of Measure for the packaging weight.")

    @fields.depends(
        'packaging_volume', 'packaging_volume_uom',
        'length', 'length_uom',
        'height', 'height_uom',
        'width', 'width_uom')
    def on_change_with_packaging_volume(self):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        Uom = pool.get('product.uom')

        if not all([self.packaging_volume_uom,
                    self.length, self.length_uom,
                    self.height, self.height_uom,
                    self.width, self.width_uom]):
            if all([
                        self.length,
                        self.height,
                        self.width]):
                return
            return self.packaging_volume

        meter = Uom(ModelData.get_id('product', 'uom_meter'))
        cubic_meter = Uom(ModelData.get_id('product', 'uom_cubic_meter'))

        length = Uom.compute_qty(
            self.length_uom, self.length, meter, round=False)
        height = Uom.compute_qty(
            self.height_uom, self.height, meter, round=False)
        width = Uom.compute_qty(
            self.width_uom, self.width, meter, round=False)

        return Uom.compute_qty(
            cubic_meter, length * height * width, self.packaging_volume_uom)


class Package(tree(), MeasurementsMixin, ModelSQL, ModelView):
    __name__ = 'stock.package'
    _rec_name = 'number'
    number = fields.Char("Number", readonly=True, required=True)
    company = fields.Many2One('company.company', "Company", required=True)
    type = fields.Many2One(
        'stock.package.type', "Type", required=True,
        states={
            'readonly': Eval('state') == 'closed',
            })
    shipment = fields.Reference(
        "Shipment", selection='get_shipment',
        states={
            'readonly': Eval('state') == 'closed',
            },
        domain={
            'stock.shipment.out': [
                ('company', '=', Eval('company', -1)),
                ],
            'stock.shipment.in.return': [
                ('company', '=', Eval('company', -1)),
                ],
            })
    moves = fields.One2Many('stock.move', 'package', 'Moves',
        domain=[
            ('id', 'in', Eval('allowed_moves', [])),
            ],
        filter=[
            ('quantity', '!=', 0),
            ],
        add_remove=[
            ('package', '=', None),
            ],
        states={
            'readonly': Eval('state') == 'closed',
            })
    allowed_moves = fields.Function(
        fields.Many2Many('stock.move', None, None, "Allowed Moves"),
        'on_change_with_allowed_moves')
    parent = fields.Many2One(
        'stock.package', "Parent", ondelete='CASCADE',
        domain=[
            ('company', '=', Eval('company', -1)),
            ('shipment', '=', Eval('shipment')),
            ],
        states={
            'readonly': Eval('state') == 'closed',
            })
    children = fields.One2Many(
        'stock.package', 'parent', 'Children',
        domain=[
            ('company', '=', Eval('company', -1)),
            ('shipment', '=', Eval('shipment')),
            ],
        states={
            'readonly': Eval('state') == 'closed',
            })
    state = fields.Function(fields.Selection([
                ('open', "Open"),
                ('closed', "Closed"),
                ], "State"), 'on_change_with_state')

    @classmethod
    def __setup__(cls):
        cls.number.search_unaccented = False
        super().__setup__()
        for field in [
                cls.length, cls.length_uom,
                cls.height, cls.height_uom,
                cls.width, cls.width_uom,
                cls.packaging_volume, cls.packaging_volume_uom,
                cls.packaging_weight, cls.packaging_weight_uom,
                ]:
            field.states = {
                'readonly': Eval('state') == 'closed',
                }

    @classmethod
    def __register__(cls, module):
        table_h = cls.__table_handler__(module)

        # Migration from 6.8: rename code to number
        if table_h.column_exist('code'):
            table_h.column_rename('code', 'number')

        super().__register__(module)

    @classmethod
    def order_number(cls, tables):
        table, _ = tables[None]
        return [CharLength(table.number), table.number]

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @staticmethod
    def _get_shipment():
        'Return list of Model names for shipment Reference'
        return [
            'stock.shipment.out',
            'stock.shipment.in.return',
            'stock.shipment.internal',
            ]

    @classmethod
    def get_shipment(cls):
        pool = Pool()
        Model = pool.get('ir.model')
        get_name = Model.get_name
        models = cls._get_shipment()
        return [(None, '')] + [(m, get_name(m)) for m in models]

    @fields.depends('shipment')
    def on_change_with_allowed_moves(self, name=None):
        if self.shipment:
            return self.shipment.packages_moves

    @fields.depends('shipment')
    def on_change_with_state(self, name=None):
        if (self.shipment
                and self.shipment.state in {
                    'packed', 'shipped', 'done', 'cancelled'}):
            return 'closed'
        return 'open'

    @fields.depends('type')
    def on_change_type(self):
        if self.type:
            for name in dir(MeasurementsMixin):
                if isinstance(getattr(MeasurementsMixin, name), fields.Field):
                    setattr(self, name, getattr(self.type, name))

    @classmethod
    def validate(cls, packages):
        super().validate(packages)
        for package in packages:
            package.check_volume()

    def check_volume(self):
        pool = Pool()
        Uom = pool.get('product.uom')
        Lang = pool.get('ir.lang')
        lang = Lang.get()
        if not self.packaging_volume:
            return
        children_volume = 0
        for child in self.children:
            if child.packaging_volume:
                children_volume += Uom.compute_qty(
                    child.packaging_volume_uom, child.packaging_volume,
                    self.packaging_volume_uom, round=False)
        if self.packaging_volume < children_volume:
            raise PackageValidationError(
                gettext('stock_package.msg_package_volume_too_small',
                    package=self.rec_name,
                    volume=lang.format_number_symbol(
                        self.packaging_volume, self.packaging_volume_uom),
                    children_volume=lang.format_number_symbol(
                        children_volume, self.packaging_volume_uom)))

    @classmethod
    def preprocess_values(cls, mode, values):
        pool = Pool()
        Configuration = pool.get('stock.configuration')
        values = super().preprocess_values(mode, values)
        if mode == 'create' and not values.get('number'):
            company_id = values.get('company', cls.default_company())
            if company_id is not None:
                configuration = Configuration(1)
                if sequence := configuration.get_multivalue(
                        'package_sequence', company=company_id):
                    values['number'] = sequence.get()
        return values

    @classmethod
    def copy(cls, packages, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('moves')
        return super().copy(packages, default=default)


class Type(MeasurementsMixin, DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'stock.package.type'
    name = fields.Char('Name', required=True)


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'
    package = fields.Many2One(
        'stock.package', "Package", readonly=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ])

    @property
    def package_path(self):
        path = []
        package = self.package
        while package:
            path.append(package)
            package = package.parent
        path.reverse()
        return path

    @classmethod
    def copy(cls, moves, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('package')
        return super().copy(moves, default=default)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, moves):
        cls.write([m for m in moves if m.package], {'package': None})
        super().cancel(moves)


class PackageMixin(object):
    __slots__ = ()
    packages = fields.One2Many('stock.package', 'shipment', 'Packages',
        domain=[
            ('company', '=', Eval('company', -1)),
            ])
    root_packages = fields.One2Many('stock.package',
        'shipment', 'Packages',
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        filter=[
            ('parent', '=', None),
            ])

    @classmethod
    def check_packages(cls, shipments):
        for shipment in shipments:
            if not shipment.packages:
                continue
            length = sum(len(p.moves) for p in shipment.packages)
            if len(shipment.packages_moves) != length:
                raise PackageError(
                    gettext('stock_package.msg_package_mismatch',
                        shipment=shipment.rec_name))

    @property
    def packages_moves(self):
        raise NotImplementedError

    @classmethod
    def copy(cls, shipments, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('packages')
        default.setdefault('root_packages')
        return super().copy(shipments, default=default)


class ShipmentOut(PackageMixin, object, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        packages_readonly = If(
            Eval('warehouse_storage') == Eval('warehouse_output'),
            Eval('state') != 'waiting',
            Eval('state') != 'picked')
        for field in [cls.packages, cls.root_packages]:
            field.states['readonly'] = packages_readonly

    @classmethod
    @ModelView.button
    @Workflow.transition('packed')
    def pack(cls, shipments):
        super().pack(shipments)
        cls.check_packages(shipments)

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def do(cls, shipments):
        super().do(shipments)
        cls.check_packages(shipments)

    @property
    def packages_moves(self):
        return [
            m for m in self.outgoing_moves
            if m.state != 'cancelled' and m.quantity]

    def _group_parcel_key(self, lines, line):
        try:
            root_package = line.package_path[0]
        except IndexError:
            root_package = None
        return super()._group_parcel_key(lines, line) + (
            ('root_package', root_package),)

    @fields.depends('carrier')
    def _parcel_weight(self, parcel):
        pool = Pool()
        Uom = pool.get('product.uom')
        weight = super()._parcel_weight(parcel)
        if self.carrier:
            carrier_uom = self.carrier.weight_uom
            packages = {p for l in parcel for p in l.package_path}
            for package in packages:
                if package.packaging_weight:
                    weight += Uom.compute_qty(
                        package.packaging_weight_uom, package.packaging_weight,
                        carrier_uom, round=False)
        return weight


class ShipmentInReturn(PackageMixin, object, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in.return'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        packages_readonly = ~Eval('state').in_(['waiting', 'assigned'])
        for field in [cls.packages, cls.root_packages]:
            field.states['readonly'] = packages_readonly

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def do(cls, shipments):
        super().do(shipments)
        cls.check_packages(shipments)

    @property
    def packages_moves(self):
        return [
            m for m in self.moves
            if m.state != 'cancelled' and m.quantity]


class ShipmentInternal(PackageMixin, object, metaclass=PoolMeta):
    __name__ = 'stock.shipment.internal'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        packages_readonly = Eval('state') != 'waiting'
        packages_invisible = ~Eval('transit_location')
        for field in [cls.packages, cls.root_packages]:
            field.states['readonly'] = packages_readonly
            field.states['invisible'] = packages_invisible

    @classmethod
    @ModelView.button
    @Workflow.transition('packed')
    def pack(cls, shipments):
        super().pack(shipments)
        cls.check_packages(shipments)

    @property
    def packages_moves(self):
        return [
            m for m in self.outgoing_moves
            if m.state != 'cancelled' and m.quantity]
