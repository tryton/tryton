# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Cast, Literal
from sql.functions import Position, Substring

from trytond import backend
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
        return super(Configuration, cls).multivalue_model(field)

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
    def __register__(cls, module_name):
        exist = backend.TableHandler.table_exist(cls._table)
        if exist:
            table = cls.__table_handler__(module_name)
            exist &= table.column_exist('package_sequence')

        super(ConfigurationSequence, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('package_sequence')
        value_names.append('package_sequence')
        super(ConfigurationSequence, cls)._migrate_property(
            field_names, value_names, fields)

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

    packaging_length = fields.Float(
        "Packaging Length", digits='packaging_length_uom',
        help="The length of the package.")
    packaging_length_uom = fields.Many2One(
        'product.uom', "Packaging Length UOM",
        domain=[('category', '=', Id('product', 'uom_cat_length'))],
        states={
            'required': Bool(Eval('packaging_length')),
            },
        depends=['packaging_length'])
    packaging_height = fields.Float(
        "Packaging Height", digits='packaging_height_uom',
        help="The height of the package.")
    packaging_height_uom = fields.Many2One(
        'product.uom', "Packaging Height UOM",
        domain=[('category', '=', Id('product', 'uom_cat_length'))],
        states={
            'required': Bool(Eval('packaging_height')),
            },
        depends=['packaging_height'])
    packaging_width = fields.Float(
        "Packaging Width", digits='packaging_width_uom',
        help="The width of the package.")
    packaging_width_uom = fields.Many2One(
        'product.uom', "Packaging Width UOM",
        domain=[('category', '=', Id('product', 'uom_cat_length'))],
        states={
            'required': Bool(Eval('packaging_width')),
            },
        depends=['packaging_width'])

    packaging_volume = fields.Float(
        "Packaging Volume", digits='packaging_volume_uom',
        states={
            'readonly': (
                Bool(Eval('packaging_length'))
                & Bool(Eval('packaging_height'))
                & Bool(Eval('packaging_width'))),
            },
        depends=['packaging_length', 'packaging_height', 'packaging_width'],
        help="The volume of the package.")
    packaging_volume_uom = fields.Many2One(
        'product.uom', "Packaging Volume UOM",
        domain=[('category', '=', Id('product', 'uom_cat_volume'))],
        states={
            'required': Bool(Eval('packaging_volume')),
            },
        depends=['packaging_volume'])

    packaging_weight = fields.Float(
        "Packaging Weight", digits='packaging_weight_uom',
        help="The weight of the package when empty.")
    packaging_weight_uom = fields.Many2One(
        'product.uom', "Packaging Weight UOM",
        domain=[('category', '=', Id('product', 'uom_cat_weight'))],
        states={
            'required': Bool(Eval('packaging_weight')),
            })

    @fields.depends(
        'packaging_volume', 'packaging_volume_uom',
        'packaging_length', 'packaging_length_uom',
        'packaging_height', 'packaging_height_uom',
        'packaging_width', 'packaging_width_uom')
    def on_change_with_packaging_volume(self):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        Uom = pool.get('product.uom')

        if not all([self.packaging_volume_uom,
                    self.packaging_length, self.packaging_length_uom,
                    self.packaging_height, self.packaging_height_uom,
                    self.packaging_width, self.packaging_width_uom]):
            if all([
                        self.packaging_length,
                        self.packaging_height,
                        self.packaging_width]):
                return
            return self.packaging_volume

        meter = Uom(ModelData.get_id('product', 'uom_meter'))
        cubic_meter = Uom(ModelData.get_id('product', 'uom_cubic_meter'))

        length = Uom.compute_qty(
            self.packaging_length_uom, self.packaging_length, meter,
            round=False)
        height = Uom.compute_qty(
            self.packaging_height_uom, self.packaging_height, meter,
            round=False)
        width = Uom.compute_qty(
            self.packaging_width_uom, self.packaging_width, meter,
            round=False)

        return Uom.compute_qty(
            cubic_meter, length * height * width, self.packaging_volume_uom)


class Package(tree(), MeasurementsMixin, ModelSQL, ModelView):
    'Stock Package'
    __name__ = 'stock.package'
    _rec_name = 'code'
    code = fields.Char('Code', select=True, readonly=True, required=True)
    company = fields.Many2One('company.company', "Company", required=True)
    type = fields.Many2One(
        'stock.package.type', "Type", required=True,
        states={
            'readonly': Eval('state') == 'closed',
            })
    shipment = fields.Reference(
        "Shipment", selection='get_shipment', select=True,
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
            ('company', '=', Eval('company', -1)),
            ('shipment', '=', Eval('shipment')),
            ('to_location.type', 'in', ['customer', 'supplier']),
            ('state', '!=', 'cancelled'),
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
    parent = fields.Many2One(
        'stock.package', "Parent", select=True, ondelete='CASCADE',
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
    def __register__(cls, module):
        pool = Pool()
        table_h = cls.__table_handler__(module)
        table = cls.__table__()
        company_exist = table_h.column_exist('company')
        cursor = Transaction().connection.cursor()

        super().__register__(module)

        # Migration from 5.8: add company
        if not company_exist:
            shipment_id = Cast(Substring(
                    table.shipment,
                    Position(',', table.shipment) + Literal(1)),
                cls.id.sql_type().base)
            for name in cls._get_shipment():
                Shipment = pool.get(name)
                shipment = Shipment.__table__()
                value = (shipment
                    .select(shipment.company,
                        where=shipment.id == shipment_id))
                cursor.execute(*table.update(
                        [table.company], [value],
                        where=table.shipment.like(name + ',%')))

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @staticmethod
    def _get_shipment():
        'Return list of Model names for shipment Reference'
        return [
            'stock.shipment.out',
            'stock.shipment.in.return',
            ]

    @classmethod
    def get_shipment(cls):
        pool = Pool()
        Model = pool.get('ir.model')
        get_name = Model.get_name
        models = cls._get_shipment()
        return [(None, '')] + [(m, get_name(m)) for m in models]

    @fields.depends('shipment')
    def on_change_with_state(self, name=None):
        if (self.shipment
                and self.shipment.state in {'packed', 'done', 'cancelled'}):
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
    def create(cls, vlist):
        pool = Pool()
        Config = pool.get('stock.configuration')

        vlist = [v.copy() for v in vlist]
        config = Config(1)
        default_company = cls.default_company()
        for values in vlist:
            values['code'] = config.get_multivalue(
                'package_sequence',
                company=values.get('company', default_company)).get()
        return super(Package, cls).create(vlist)

    @classmethod
    def copy(cls, packages, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('moves')
        return super().copy(packages, default=default)


class Type(MeasurementsMixin, DeactivableMixin, ModelSQL, ModelView):
    'Stock Package Type'
    __name__ = 'stock.package.type'
    name = fields.Char('Name', required=True)


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'
    package = fields.Many2One(
        'stock.package', "Package", select=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        states={
            'readonly': Eval('state') == 'cancelled',
            })

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
    root_packages = fields.Function(fields.One2Many('stock.package',
            'shipment', 'Packages',
            domain=[
                ('company', '=', Eval('company', -1)),
                ('parent', '=', None),
                ]),
        'get_root_packages', setter='set_root_packages')

    def get_root_packages(self, name):
        return [p.id for p in self.packages if not p.parent]

    @classmethod
    def set_root_packages(cls, shipments, name, value):
        if not value:
            return
        cls.write(shipments, {
                'packages': value,
                })

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
        super(ShipmentOut, cls).pack(shipments)
        cls.check_packages(shipments)

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def done(cls, shipments):
        super(ShipmentOut, cls).done(shipments)
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
    def done(cls, shipments):
        super(ShipmentInReturn, cls).done(shipments)
        cls.check_packages(shipments)

    @property
    def packages_moves(self):
        return [
            m for m in self.moves
            if m.state != 'cancelled' and m.quantity]
