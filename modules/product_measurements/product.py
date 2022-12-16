#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval, Bool, Id
from trytond.pool import PoolMeta

__all__ = ['Template']
__metaclass__ = PoolMeta

NON_MEASURABLE = ['service']


class Template:
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
    length_digits = fields.Function(fields.Integer('Length Digits',
            on_change_with=['length_uom']), 'on_change_with_length_digits')
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
    height_digits = fields.Function(fields.Integer('Height Digits',
            on_change_with=['height_uom']), 'on_change_with_height_digits')
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
    width_digits = fields.Function(fields.Integer('Width Digits',
            on_change_with=['width_uom']), 'on_change_with_width_digits')
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
    weight_digits = fields.Function(fields.Integer('Weight Digits',
            on_change_with=['weight_uom']), 'on_change_with_weight_digits')

    def on_change_with_length_digits(self, name=None):
        return (self.length_uom.digits if self.length_uom
            else self.default_length_digits())

    @staticmethod
    def default_length_digits():
        return 2

    def on_change_with_height_digits(self, name=None):
        return (self.height_uom.digits if self.height_uom
            else self.default_height_digits())

    @staticmethod
    def default_height_digits():
        return 2

    def on_change_with_width_digits(self, name=None):
        return (self.width_uom.digits if self.width_uom
            else self.default_width_digits())

    @staticmethod
    def default_width_digits():
        return 2

    def on_change_with_weight_digits(self, name=None):
        return (self.weight_uom.digits if self.weight_uom
            else self.default_weight_digits())

    @staticmethod
    def default_weight_digits():
        return 2
