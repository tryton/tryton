# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval, Bool, Id
from trytond.pool import PoolMeta, Pool

NON_MEASURABLE = ['service']


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'

    length = fields.Float(
        "Length", digits='length_uom',
        states={
            'invisible': Eval('type').in_(NON_MEASURABLE),
            },
        depends=['type'])
    length_uom = fields.Many2One('product.uom', 'Length Uom',
        domain=[('category', '=', Id('product', 'uom_cat_length'))],
        states={
            'invisible': Eval('type').in_(NON_MEASURABLE),
            'required': Bool(Eval('length')),
            },
        depends=['type', 'length'])
    height = fields.Float(
        "Height", digits='height_uom',
        states={
            'invisible': Eval('type').in_(NON_MEASURABLE),
            },
        depends=['type'])
    height_uom = fields.Many2One('product.uom', 'Height Uom',
        domain=[('category', '=', Id('product', 'uom_cat_length'))],
        states={
            'invisible': Eval('type').in_(NON_MEASURABLE),
            'required': Bool(Eval('height')),
            },
        depends=['type', 'height'])
    width = fields.Float(
        "Width", digits='width_uom',
        states={
            'invisible': Eval('type').in_(NON_MEASURABLE),
            },
        depends=['type'])
    width_uom = fields.Many2One('product.uom', 'Width Uom',
        domain=[('category', '=', Id('product', 'uom_cat_length'))],
        states={
            'invisible': Eval('type').in_(NON_MEASURABLE),
            'required': Bool(Eval('width')),
            },
        depends=['type', 'width'])
    volume = fields.Float(
        "Volume", digits='volume_uom',
        states={
            'invisible': Eval('type').in_(NON_MEASURABLE),
            'readonly': (Bool(Eval('length'))
                & Bool(Eval('height')) & Bool(Eval('width'))),
            },
        depends=['type'])
    volume_uom = fields.Many2One('product.uom', 'Volume Uom',
        domain=[('category', '=', Id('product', 'uom_cat_volume'))],
        states={
            'invisible': Eval('type').in_(NON_MEASURABLE),
            'required': Bool(Eval('volume')),
            },
        depends=['type', 'volume'])
    weight = fields.Float(
        "Weight", digits='weight_uom',
        states={
            'invisible': Eval('type').in_(NON_MEASURABLE),
            },
        depends=['type'])
    weight_uom = fields.Many2One('product.uom', 'Weight Uom',
        domain=[('category', '=', Id('product', 'uom_cat_weight'))],
        states={
            'invisible': Eval('type').in_(NON_MEASURABLE),
            'required': Bool(Eval('weight')),
            },
        depends=['type', 'weight'])

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
        return super(Template, cls).view_attributes() + [
            ('//page[@id="measurements"]', 'states', {
                    'invisible': Eval('type').in_(NON_MEASURABLE),
                    })]


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'
