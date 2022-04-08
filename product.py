# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
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
            })
    attributes_name = fields.Function(fields.Char(
            "Attributes Name",
            states={
                'invisible': ~Eval('attribute_set'),
                }),
        'on_change_with_attributes_name')

    attribute_set = fields.Function(
        fields.Many2One('product.attribute.set', "Attribute Set"),
        'on_change_with_attribute_set')

    @fields.depends('template', '_parent_template.attribute_set')
    def on_change_with_attribute_set(self, name=None):
        if self.template and self.template.attribute_set:
            return self.template.attribute_set.id

    @fields.depends('attribute_set', 'attributes')
    def on_change_with_attributes_name(self, name=None):
        if not self.attribute_set or not self.attributes:
            return

        def key(attribute):
            return getattr(attribute, 'sequence', attribute.name)

        values = []
        for attribute in sorted(self.attribute_set.attributes, key=key):
            if attribute.name in self.attributes:
                value = self.attributes[attribute.name]
                values.append(gettext('product_attribute.msg_label_value',
                        label=attribute.string,
                        value=attribute.format(value)))
        return " | ".join(filter(None, values))
