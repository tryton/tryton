# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from decimal import Decimal

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, Id

NON_MEASURABLE = ['service']


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'

    length = fields.Float(
        "Length", digits='length_uom',
        states={
            'invisible': Eval('type').in_(NON_MEASURABLE),
            },
        help="Length for 1 default unit of measure.")
    length_uom = fields.Many2One(
        'product.uom', "Length UoM",
        domain=[('category', '=', Id('product', 'uom_cat_length'))],
        states={
            'invisible': Eval('type').in_(NON_MEASURABLE),
            'required': Bool(Eval('length')),
            },
        help="The Unit of Measure for the length.")
    height = fields.Float(
        "Height", digits='height_uom',
        states={
            'invisible': Eval('type').in_(NON_MEASURABLE),
            },
        help="Height for 1 default unit of measure.")
    height_uom = fields.Many2One(
        'product.uom', 'Height UoM',
        domain=[('category', '=', Id('product', 'uom_cat_length'))],
        states={
            'invisible': Eval('type').in_(NON_MEASURABLE),
            'required': Bool(Eval('height')),
            },
        help="The Unit of Measure for the height.")
    width = fields.Float(
        "Width", digits='width_uom',
        states={
            'invisible': Eval('type').in_(NON_MEASURABLE),
            },
        help="Width for 1 default unit of measure.")
    width_uom = fields.Many2One(
        'product.uom', 'Width UoM',
        domain=[('category', '=', Id('product', 'uom_cat_length'))],
        states={
            'invisible': Eval('type').in_(NON_MEASURABLE),
            'required': Bool(Eval('width')),
            },
        help="The Unit of Measure for the width.")
    volume = fields.Float(
        "Volume", digits='volume_uom',
        states={
            'invisible': Eval('type').in_(NON_MEASURABLE),
            'readonly': (Bool(Eval('length'))
                & Bool(Eval('height')) & Bool(Eval('width'))),
            },
        help="Volume for 1 default unit of measure.")
    volume_uom = fields.Many2One(
        'product.uom', "Volume UoM",
        domain=[('category', '=', Id('product', 'uom_cat_volume'))],
        states={
            'invisible': Eval('type').in_(NON_MEASURABLE),
            'required': Bool(Eval('volume')),
            },
        help="The Unit of Measure for the volume.")
    weight = fields.Float(
        "Weight", digits='weight_uom',
        states={
            'invisible': Eval('type').in_(NON_MEASURABLE),
            },
        help="Weight for 1 default unit of measure.")
    weight_uom = fields.Many2One('product.uom', 'Weight UoM',
        domain=[('category', '=', Id('product', 'uom_cat_weight'))],
        states={
            'invisible': Eval('type').in_(NON_MEASURABLE),
            'required': Bool(Eval('weight')),
            },
        help="The Unit of Measure for the weight.")

    @fields.depends('volume', 'volume_uom',
        'length', 'length_uom',
        'height', 'height_uom',
        'width', 'width_uom')
    def on_change_with_volume(self):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        Uom = pool.get('product.uom')

        if not all([self.volume_uom, self.length, self.length_uom,
                    self.height, self.height_uom, self.width, self.width_uom]):
            if all([self.length, self.height, self.width]):
                return
            return self.volume

        meter = Uom(ModelData.get_id('product', 'uom_meter'))
        cubic_meter = Uom(ModelData.get_id('product', 'uom_cubic_meter'))

        length = Uom.compute_qty(
            self.length_uom, self.length, meter, round=False)
        height = Uom.compute_qty(
            self.height_uom, self.height, meter, round=False)
        width = Uom.compute_qty(
            self.width_uom, self.width, meter, round=False)

        return Uom.compute_qty(
            cubic_meter, length * height * width, self.volume_uom)

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('//page[@id="measurements"]', 'states', {
                    'invisible': Eval('type').in_(NON_MEASURABLE),
                    })]


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'


class PriceList(metaclass=PoolMeta):
    __name__ = 'product.price_list'

    def get_context_formula(self, product, quantity, uom, pattern=None):
        pool = Pool()
        UoM = pool.get('product.uom')
        ModelData = pool.get('ir.model.data')

        liter = UoM(ModelData.get_id('product', 'uom_liter'))
        kilogram = UoM(ModelData.get_id('product', 'uom_kilogram'))

        context = super().get_context_formula(
            product, quantity, uom, pattern=pattern)
        volume = weight = 0
        if product:
            if product.volume is not None:
                volume = UoM.compute_qty(
                    product.volume_uom, product.volume, liter, round=False)
            if product.weight is not None:
                weight = UoM.compute_qty(
                    product.weight_uom, product.weight, kilogram, round=False)
        context['names']['volume'] = Decimal(str(volume))
        context['names']['weight'] = Decimal(str(weight))
        return context


class PriceListLine(metaclass=PoolMeta):
    __name__ = 'product.price_list.line'

    volume_uom = fields.Many2One(
        'product.uom', "Volume UoM",
        domain=[('category', '=', Id('product', 'uom_cat_volume'))],
        help="Leave empty for liter.")
    weight_uom = fields.Many2One(
        'product.uom', "Weight UoM",
        domain=[('category', '=', Id('product', 'uom_cat_weight'))],
        help="Leave empty for kilogram.")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.formula.help += ("\n"
            "-volume: the volume of 1 unit of product\n"
            "-weight: the weight of 1 unit of product")

    def get_unit_price(self, **context):
        pool = Pool()
        UoM = pool.get('product.uom')
        ModelData = pool.get('ir.model.data')

        if self.volume_uom:
            context['names'] = context['names'].copy()
            liter = UoM(ModelData.get_id('product', 'uom_liter'))
            volume = UoM.compute_qty(
                liter, float(context['names']['volume']), self.volume_uom,
                round=False)
            context['names']['volume'] = Decimal(str(volume))
        if self.weight_uom:
            context['names'] = context['names'].copy()
            kilogram = UoM(ModelData.get_id('product', 'uom_kilogram'))
            weight = UoM.compute_qty(
                kilogram, float(context['names']['weight']), self.weight_uom,
                round=False)
            context['names']['weight'] = Decimal(str(weight))
        return super().get_unit_price(**context)
