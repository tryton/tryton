# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.i18n import gettext
from trytond.model import fields
from trytond.modules.product import uom_conversion_digits
from trytond.modules.product.exceptions import UOMValidationError
from trytond.pool import PoolMeta
from trytond.pyson import Bool, Eval


class SaleSecondaryMixin:
    __slots__ = ()
    sale_secondary_uom = fields.Many2One(
        'product.uom', "Sale Secondary UOM",
        domain=[
            ('category', '!=', Eval('default_uom_category')),
            ])
    sale_secondary_uom_factor = fields.Float(
        "Sale Secondary UOM Factor", digits=uom_conversion_digits,
        states={
            'required': Bool(Eval('sale_secondary_uom')),
            'invisible': ~Eval('sale_secondary_uom'),
            },
        help="The coefficient for the formula:\n"
        "1 (sale unit) = coefficient (secondary unit)")
    sale_secondary_uom_rate = fields.Float(
        "Sale Secondary UOM Rate", digits=uom_conversion_digits,
        states={
            'required': Bool(Eval('sale_secondary_uom')),
            'invisible': ~Eval('sale_secondary_uom'),
            },
        help="The coefficient for the formula:\n"
        "coefficient (sale unit) = 1 (secondary unit)")
    sale_secondary_uom_category = fields.Function(
        fields.Many2One('product.uom.category', "Sale Secondary UOM Category"),
        'on_change_with_sale_secondary_uom_category',
        searcher='search_sale_secondary_uom_category')

    @fields.depends('sale_secondary_uom_factor')
    def on_change_sale_secondary_uom_factor(self):
        if not self.sale_secondary_uom_factor:
            self.sale_secondary_uom_rate = None
        else:
            self.sale_secondary_uom_rate = round(
                1. / self.sale_secondary_uom_factor, uom_conversion_digits[1])

    @fields.depends('sale_secondary_uom_rate')
    def on_change_sale_secondary_uom_rate(self):
        if not self.sale_secondary_uom_rate:
            self.sale_secondary_uom_factor = None
        else:
            self.sale_secondary_uom_factor = round(
                1. / self.sale_secondary_uom_rate, uom_conversion_digits[1])

    @fields.depends('sale_secondary_uom')
    def on_change_with_sale_secondary_uom_category(self, name=None):
        if self.sale_secondary_uom:
            return self.sale_secondary_uom.category.id

    @classmethod
    def search_sale_secondary_uom_category(cls, name, clause):
        return [('sale_secondary_uom.category' + clause[0].lstrip(name),)
            + tuple(clause[1:])]

    @property
    def sale_secondary_uom_normal_rate(self):
        uom = self.sale_secondary_uom
        rate = self.sale_secondary_uom_rate
        if self.sale_uom and rate and uom:
            if self.sale_uom.accurate_field == 'factor':
                rate *= self.sale_uom.factor
            else:
                rate /= self.sale_uom.rate
            if uom.accurate_field == 'factor':
                rate /= uom.factor
            else:
                rate *= uom.rate
        return rate

    @property
    def sale_secondary_uom_normal_factor(self):
        uom = self.sale_secondary_uom
        factor = self.sale_secondary_uom_factor
        if uom and factor and self.sale_uom:
            if uom.accurate_field == 'factor':
                factor *= uom.factor
            else:
                factor /= uom.rate
            if self.sale_uom.accurate_field == 'factor':
                factor /= self.sale_uom.factor
            else:
                factor *= self.sale_uom.rate
        return factor

    @classmethod
    def validate_fields(cls, records, field_names):
        super().validate_fields(records, field_names)
        cls.check_sale_secondary_uom_factor_and_rate(records, field_names)

    @classmethod
    def check_sale_secondary_uom_factor_and_rate(
            cls, records, field_names=None):
        if field_names and not (field_names & {
                    'sale_secondary_uom_factor', 'sale_secondary_uom_rate'}):
            return
        for record in records:
            factor = record.sale_secondary_uom_factor
            rate = record.sale_secondary_uom_rate
            if factor and rate:
                new_rate = round(1. / factor, uom_conversion_digits[1])
                new_factor = round(1. / rate, uom_conversion_digits[1])
                if rate != new_rate and factor != new_factor:
                    raise UOMValidationError(
                        gettext('sale_secondary_unit'
                            '.msg_sale_secondary_uom_incompatible_factor_rate',
                            record=record.rec_name))


class Template(SaleSecondaryMixin, metaclass=PoolMeta):
    __name__ = 'product.template'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.sale_secondary_uom.states = {
            'invisible': ~Eval('salable', False),
            }


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    @property
    def sale_secondary_uom_normal_rate(self):
        return self.template.sale_secondary_uom_normal_rate

    @property
    def sale_secondary_uom_normal_factor(self):
        return self.template.sale_secondary_uom_normal_factor


class ProductCustomer(SaleSecondaryMixin, metaclass=PoolMeta):
    __name__ = 'sale.product_customer'

    default_uom_category = fields.Function(
        fields.Many2One('product.uom.category', "Default UOM Category"),
        'on_change_with_default_uom_category')

    @fields.depends('template', '_parent_template.sale_uom',
        'product', '_parent_product.sale_uom')
    def on_change_with_default_uom_category(self, name=None):
        if self.product and self.product.sale_uom:
            return self.product.sale_uom.category.id
        elif self.template and self.template.sale_uom:
            return self.template.sale_uom.category.id

    @property
    def sale_uom(self):
        if self.product and self.product.sale_uom:
            return self.product.sale_uom
        elif self.template and self.template.sale_uom:
            return self.template.sale_uom
