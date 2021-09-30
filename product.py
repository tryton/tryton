# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    @property
    def images_used(self):
        for image in super().images_used:
            if not image.product and image.attributes:
                if not self.attributes:
                    continue
                for key, value in image.attributes.items():
                    if value != self.attributes.get(key):
                        break
                else:
                    yield image
            else:
                yield image


class Image(metaclass=PoolMeta):
    __name__ = 'product.image'

    attributes = fields.Dict('product.attribute', "Attributes",
        domain=[
            ('sets', '=', Eval('attribute_set', -1)),
            ],
        states={
            'invisible': ~Eval('attribute_set') | Eval('product'),
            },
        depends=['attribute_set', 'product'])

    attribute_set = fields.Function(
        fields.Many2One('product.attribute.set', "Attribute Set"),
        'on_change_with_attribute_set')

    @fields.depends('template', '_parent_template.attribute_set')
    def on_change_with_attribute_set(self, name=None):
        if self.template and self.template.attribute_set:
            return self.template.attribute_set.id
