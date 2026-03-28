# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from itertools import groupby

from sql import Null
from sql.conditionals import Coalesce

from trytond.model import Check, ModelSQL, fields
from trytond.modules.company.model import CompanyValueMixin
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Id


class Configuration(metaclass=PoolMeta):
    __name__ = 'stock.configuration'

    ethanol_volume_uom = fields.MultiValue(
        fields.Many2One(
            'product.uom', "Alcohol Volume UoM", required=True,
            domain=[('category', '=', Id('product', 'uom_cat_volume'))]))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'ethanol_volume_uom':
            return pool.get('stock.configuration.ethanol')
        return super().multivalue_model(field)

    @classmethod
    def default_ethanol_volume_uom(cls, **pattern):
        model = cls.multivalue_model('ethanol_volume_uom')
        return model.default_ethanol_volume_uom()


class ConfigurationEthanol(ModelSQL, CompanyValueMixin):
    "Stock Configuration Ethanol"
    __name__ = 'stock.configuration.ethanol'

    ethanol_volume_uom = fields.Many2One(
        'product.uom', "Ethanol Volume UoM", required=True,
        domain=[('category', '=', Id('product', 'uom_cat_volume'))])

    @classmethod
    def default_ethanol_volume_uom(cls):
        pool = Pool()
        UoM = pool.get('product.uom')
        ModelData = pool.get('ir.model.data')
        return UoM(ModelData.get_id('product', 'uom_liter')).id


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    contain_ethanol = fields.Function(
        fields.Boolean("Contain Alcohol"),
        'on_change_with_contain_ethanol', searcher='search_contain_ethanol')
    ethanol_by_volume = fields.Function(fields.Float(
            "Alcohol By Volume", digits=(1, 4),
            states={
                'invisible': ~Eval('contain_ethanol'),
                },
            help="How much ethanol/alcohol is contained "
            "in a given volume at 20°C."),
        'on_change_with_ethanol_by_volume')
    internal_ethanol_volume = fields.Float(
        "Internal Alcohol Volume", readonly=True,
        states={
            'invisible': ~Eval('ethanol_volume_required', False),
            'required': Eval('ethanol_volume_required', False),
            },
        help="The volume of ethanol/alcohol moved in liter.")
    ethanol_volume = fields.Function(
        fields.Float(
            "Alcohol Volume", digits='ethanol_volume_unit',
            states={
                'invisible': ~Eval('ethanol_volume_required'),
                },
            help="The volume of ethanol/alcohol moved."),
        'get_ethanol_volume')
    ethanol_volume_unit = fields.Function(
        fields.Many2One(
            'product.uom', "Alcohol Volume UoM",
            states={
                'invisible': ~Eval('ethanol_volume_required'),
                }),
        'get_ethanol_volume_unit')
    ethanol_volume_required = fields.Function(
        fields.Boolean("Alcohol Volume Required"),
        'on_change_with_ethanol_volume_required',
        searcher='search_ethanol_volume_required')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('check_move_internal_ethanol_volume_pos',
                Check(t,
                    (t.internal_ethanol_volume == Null)
                    | (t.internal_ethanol_volume >= 0)),
                'stock.msg_move_internal_ethanol_volume_positive'),
            ]

    @fields.depends('product')
    def on_change_with_contain_ethanol(self, name=None):
        if self.product:
            return self.product.contain_ethanol

    @classmethod
    def search_contain_ethanol(cls, name, clause):
        return [('product.' + clause[0], *clause[1:])]

    @fields.depends('product')
    def on_change_with_ethanol_by_volume(self, name=None):
        if self.product:
            return self.product.ethanol_by_volume_used

    @classmethod
    def order_ethanol_by_volume(cls, tables):
        pool = Pool()
        Product = pool.get('product.product')
        Template = pool.get('product.template')
        table, _ = tables[None]
        if 'product' not in tables:
            product = Product.__table__()
            product_tables = tables['product'] = {
                None: (product, table.product == product.id),
                }
        else:
            product_tables = tables['product']
        if 'template' not in product_tables:
            template = Template.__table__()
            product_tables['template'] = {
                None: (template, product.template == template.id),
                }
        else:
            template, _ = product_tables['template']
        return [
            Coalesce(product.ethanol_by_volume, template.ethanol_by_volume)]

    @classmethod
    def get_ethanol_volume(cls, moves, name):
        pool = Pool()
        UoM = pool.get('product.uom')
        ModelData = pool.get('ir.model.data')

        liter = UoM(ModelData.get_id('product', 'uom_liter'))
        volumes = {}
        for move in moves:
            if move.internal_ethanol_volume is not None:
                volume = UoM.compute_qty(
                    liter, move.internal_ethanol_volume,
                    move.ethanol_volume_unit)
            else:
                volume = None
            volumes[move.id] = volume
        return volumes

    @classmethod
    def get_ethanol_volume_unit(cls, moves, name):
        pool = Pool()
        Configuration = pool.get('stock.configuration')
        configuration = Configuration(1)
        units = {}
        for company, moves in groupby(moves, key=lambda m: m.company):
            uom = configuration.get_multivalue(
                'ethanol_volume_uom', company=company.id)
            for move in moves:
                units[move.id] = uom.id
        return units

    @fields.depends('product')
    def on_change_with_ethanol_volume_required(self, name=None):
        if self.product:
            return self.product.contain_ethanol

    @classmethod
    def search_ethanol_volume_required(cls, name, clause):
        return [('product.contain_ethanol', *clause[1:])]

    @classmethod
    def default_internal_ethanol_volume(cls):
        # default value before compute of the field
        return 0

    @fields.depends('product', methods=['on_change_with_internal_quantity'])
    def on_change_with_internal_ethanol_volume(self):
        pool = Pool()
        UoM = pool.get('product.uom')
        ModelData = pool.get('ir.model.data')

        liter = UoM(ModelData.get_id('product', 'uom_liter'))
        quantity = self.on_change_with_internal_quantity()
        if quantity is not None and self.product:
            return self.product.compute_ethanol_volume(
                quantity, self.product.default_uom, liter, round=False)

    def compute_fields(self, field_names=None):
        cls = self.__class__
        values = super().compute_fields(field_names=field_names)
        if (field_names is None
                or (cls.internal_ethanol_volume.on_change_with & field_names)):
            internal_ethanol_volume = (
                self.on_change_with_internal_ethanol_volume())
            if (getattr(self, 'internal_ethanol_volume', None)
                    != internal_ethanol_volume):
                values['internal_ethanol_volume'] = internal_ethanol_volume
        return values


class ProductsByLocations(metaclass=PoolMeta):
    __name__ = 'stock.products_by_locations'

    ethanol_volume = fields.Function(
        fields.Float(
            "Alcohol Volume", digits='ethanol_volume_unit'),
        'get_product', searcher='search_product')
    ethanol_volume_unit = fields.Function(
        fields.Many2One('product.uom', "Alcohol Volume UoM"),
        'get_product')
