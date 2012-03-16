#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import Model, fields
from trytond.pyson import Eval, Bool, Id
from trytond.pool import Pool

NON_MEASURABLE = ['service']


class Template(Model):
    _name = 'product.template'

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
            on_change_with=['length_uom']), 'get_field_digits')
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
            on_change_with=['height_uom']), 'get_field_digits')
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
            on_change_with=['width_uom']), 'get_field_digits')
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
            on_change_with=['weight_uom']), 'get_field_digits')

    def _on_change_with_field_digits(self, uom_id):
        uom_obj = Pool().get('product.uom')
        if uom_id:
            uom = uom_obj.browse(uom_id)
            return uom.digits
        return 2

    def on_change_with_length_digits(self, values):
        return self._on_change_with_field_digits(values.get('length_uom'))

    def default_length_digits(self):
        return 2

    def on_change_with_height_digits(self, values):
        return self._on_change_with_field_digits(values.get('height_uom'))

    def default_height_digits(self):
        return 2

    def on_change_with_width_digits(self, values):
        return self._on_change_with_field_digits(values.get('width_uom'))

    def default_width_digits(self):
        return 2

    def on_change_with_weight_digits(self, values):
        return self._on_change_with_field_digits(values.get('weight_uom'))

    def default_weight_digits(self):
        return 2

    def get_field_digits(self, ids, name):
        digits = {}
        field = '%s_uom' % name[:-7]
        for template in self.browse(ids):
            uom = getattr(template, field)
            if uom:
                digits[template.id] = uom.digits
            else:
                digits[template.id] = 2
        return digits

Template()
