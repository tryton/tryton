# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.i18n import gettext
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool

from trytond.modules.product import uom_conversion_digits
from trytond.modules.product.exceptions import UOMValidationError


class PurchaseSecondaryMixin:
    __slots__ = ()
    purchase_secondary_uom = fields.Many2One(
        'product.uom', "Purchase Secondary UOM",
        domain=[
            ('category', '!=', Eval('default_uom_category')),
            ],
        depends=['default_uom_category'])
    purchase_secondary_uom_factor = fields.Float(
        "Purchase Secondary UOM Factor", digits=uom_conversion_digits,
        states={
            'required': Bool(Eval('purchase_secondary_uom')),
            'invisible': ~Eval('purchase_secondary_uom'),
            },
        depends=['purchase_secondary_uom'],
        help="The coefficient for the formula:\n"
        "1 (purchase unit) = coefficient (secondary unit)")
    purchase_secondary_uom_rate = fields.Float(
        "Purchase Secondary UOM Rate", digits=uom_conversion_digits,
        states={
            'required': Bool(Eval('purchase_secondary_uom')),
            'invisible': ~Eval('purchase_secondary_uom'),
            },
        depends=['purchase_secondary_uom'],
        help="The coefficient for the formula:\n"
        "coefficient (purchase unit) = 1 (secondary unit)")

    @fields.depends('purchase_secondary_uom_factor')
    def on_change_purchase_secondary_uom_factor(self):
        if not self.purchase_secondary_uom_factor:
            self.purchase_secondary_uom_rate = None
        else:
            self.purchase_secondary_uom_rate = round(
                1. / self.purchase_secondary_uom_factor,
                uom_conversion_digits[1])

    @fields.depends('purchase_secondary_uom_rate')
    def on_change_purchase_secondary_uom_rate(self):
        if not self.purchase_secondary_uom_rate:
            self.purchase_secondary_uom_factor = None
        else:
            self.purchase_secondary_uom_factor = round(
                1. / self.purchase_secondary_uom_rate,
                uom_conversion_digits[1])

    @property
    def purchase_secondary_uom_normal_rate(self):
        uom = self.purchase_secondary_uom
        rate = self.purchase_secondary_uom_rate
        if self.purchase_uom and rate and uom:
            if self.purchase_uom.accurate_field == 'factor':
                rate *= self.purchase_uom.factor
            else:
                rate /= self.purchase_uom.rate
            if uom.accurate_field == 'factor':
                rate /= uom.factor
            else:
                rate *= uom.rate
        return rate

    @property
    def purchase_secondary_uom_normal_factor(self):
        uom = self.purchase_secondary_uom
        factor = self.purchase_secondary_uom_factor
        if self.purchase_uom and factor and uom:
            if uom.accurate_field == 'factor':
                factor *= uom.factor
            else:
                factor /= uom.rate
            if self.purchase_uom.accurate_field == 'factor':
                factor /= self.purchase_uom.factor
            else:
                factor *= self.purchase_uom.rate
        return factor

    @classmethod
    def validate(cls, records):
        super().validate(records)
        for record in records:
            record.check_purchase_secondary_uom_factor_and_rate()

    def check_purchase_secondary_uom_factor_and_rate(self):
        factor = self.purchase_secondary_uom_factor
        rate = self.purchase_secondary_uom_rate
        if factor and rate:
            if ((rate != round(1. / factor, uom_conversion_digits[1]))
                    and factor != round(1. / rate, uom_conversion_digits[1])):
                raise UOMValidationError(
                    gettext('purchase_secondary_unit'
                        '.msg_secondary_uom_incompatible_factor_rate',
                        record=self))


class Template(PurchaseSecondaryMixin, metaclass=PoolMeta):
    __name__ = 'product.template'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.purchase_secondary_uom.states = {
            'readonly': ~Eval('active', True),
            'invisible': ~Eval('purchasable', False),
            }
        cls.purchase_secondary_uom.depends += ['active', 'purchasable']


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    @property
    def purchase_secondary_uom_normal_rate(self):
        return self.template.purchase_secondary_uom_normal_rate

    @property
    def purchase_secondary_uom_normal_factor(self):
        return self.template.purchase_secondary_uom_normal_factor


class ProductSupplier(PurchaseSecondaryMixin, metaclass=PoolMeta):
    __name__ = 'purchase.product_supplier'

    default_uom_category = fields.Function(
        fields.Many2One('product.uom.category', "Default UOM Category"),
        'on_change_with_default_uom_category')

    @fields.depends('template', '_parent_template.purchase_uom',
        'product', '_parent_product.purchase_uom')
    def on_change_with_default_uom_category(self, name=None):
        if self.product and self.product.purchase_uom:
            return self.product.purchase_uom.category.id
        elif self.template and self.template.purchase_uom:
            return self.template.purchase_uom.category.id

    @property
    def purchase_uom(self):
        if self.product and self.product.purchase_uom:
            return self.product.purchase_uom
        elif self.template and self.template.purchase_uom:
            return self.template.purchase_uom
