# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval, Bool, Id
from trytond.pool import PoolMeta, Pool

NON_MEASURABLE = ['service']


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'

    length = fields.Float('Length',
        digits=(16, Eval('length_digits', 2)),
        states={
            'invisible': Eval('type').in_(NON_MEASURABLE),
            },
        depends=['type', 'length_digits'])
    length_uom = fields.Many2One('product.uom', 'Length Uom',
        domain=[('category', '=', Id('product', 'uom_cat_length'))],
        states={
            'invisible': Eval('type').in_(NON_MEASURABLE),
            'required': Bool(Eval('length')),
            },
        depends=['type', 'length'])
    length_digits = fields.Function(fields.Integer('Length Digits'),
        'on_change_with_length_digits')
    height = fields.Float('Height',
        digits=(16, Eval('height_digits', 2)),
        states={
            'invisible': Eval('type').in_(NON_MEASURABLE),
            },
        depends=['type', 'height_digits'])
    height_uom = fields.Many2One('product.uom', 'Height Uom',
        domain=[('category', '=', Id('product', 'uom_cat_length'))],
        states={
            'invisible': Eval('type').in_(NON_MEASURABLE),
            'required': Bool(Eval('height')),
            },
        depends=['type', 'height'])
    height_digits = fields.Function(fields.Integer('Height Digits'),
        'on_change_with_height_digits')
    width = fields.Float('Width',
        digits=(16, Eval('width_digits', 2)),
        states={
            'invisible': Eval('type').in_(NON_MEASURABLE),
            },
        depends=['type', 'width_digits'])
    width_uom = fields.Many2One('product.uom', 'Width Uom',
        domain=[('category', '=', Id('product', 'uom_cat_length'))],
        states={
            'invisible': Eval('type').in_(NON_MEASURABLE),
            'required': Bool(Eval('width')),
            },
        depends=['type', 'width'])
    width_digits = fields.Function(fields.Integer('Width Digits'),
        'on_change_with_width_digits')
    volume = fields.Float('Volume',
        digits=(16, Eval('volume_digits', 2)),
        states={
            'invisible': Eval('type').in_(NON_MEASURABLE),
            'readonly': (Bool(Eval('length'))
                & Bool(Eval('height')) & Bool(Eval('width'))),
            },
        depends=['type', 'volume_digits'])
    volume_uom = fields.Many2One('product.uom', 'Volume Uom',
        domain=[('category', '=', Id('product', 'uom_cat_volume'))],
        states={
            'invisible': Eval('type').in_(NON_MEASURABLE),
            'required': Bool(Eval('volume')),
            },
        depends=['type', 'volume'])
    volume_digits = fields.Function(fields.Integer('Volume Digits'),
        'on_change_with_volume_digits')
    weight = fields.Float('Weight',
        digits=(16, Eval('weight_digits', 2)),
        states={
            'invisible': Eval('type').in_(NON_MEASURABLE),
            },
        depends=['type', 'weight_digits'])
    weight_uom = fields.Many2One('product.uom', 'Weight Uom',
        domain=[('category', '=', Id('product', 'uom_cat_weight'))],
        states={
            'invisible': Eval('type').in_(NON_MEASURABLE),
            'required': Bool(Eval('weight')),
            },
        depends=['type', 'weight'])
    weight_digits = fields.Function(fields.Integer('Weight Digits'),
        'on_change_with_weight_digits')

    @fields.depends('length_uom')
    def on_change_with_length_digits(self, name=None):
        return (self.length_uom.digits if self.length_uom
            else self.default_length_digits())

    @staticmethod
    def default_length_digits():
        return 2

    @fields.depends('height_uom')
    def on_change_with_height_digits(self, name=None):
        return (self.height_uom.digits if self.height_uom
            else self.default_height_digits())

    @staticmethod
    def default_height_digits():
        return 2

    @fields.depends('width_uom')
    def on_change_with_width_digits(self, name=None):
        return (self.width_uom.digits if self.width_uom
            else self.default_width_digits())

    @staticmethod
    def default_width_digits():
        return 2

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

    @fields.depends('volume_uom')
    def on_change_with_volume_digits(self, name=None):
        return (self.volume_uom.digits if self.volume_uom
            else self.default_volume_digits())

    @staticmethod
    def default_volume_digits():
        return 2

    @fields.depends('weight_uom')
    def on_change_with_weight_digits(self, name=None):
        return (self.weight_uom.digits if self.weight_uom
            else self.default_weight_digits())

    @staticmethod
    def default_weight_digits():
        return 2

    @classmethod
    def view_attributes(cls):
        return super(Template, cls).view_attributes() + [
            ('//page[@id="measurements"]', 'states', {
                    'invisible': Eval('type').in_(NON_MEASURABLE),
                    })]


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'
