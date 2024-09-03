# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import category, configuration, ir, product, uom
from .product import (
    ProductDeactivatableMixin, TemplateDeactivatableMixin, price_digits,
    round_price)
from .uom import uom_conversion_digits

__all__ = [price_digits, round_price, uom_conversion_digits,
    ProductDeactivatableMixin, TemplateDeactivatableMixin]


def register():
    Pool.register(
        ir.Configuration,
        ir.Cron,
        uom.UomCategory,
        uom.Uom,
        category.Category,
        product.Template,
        product.Product,
        product.ProductIdentifier,
        product.ProductListPrice,
        # before ProductCostPrice for migration
        product.ProductCostPriceMethod,
        product.ProductCostPrice,
        product.TemplateCategory,
        product.TemplateCategoryAll,
        product.ProductReplaceAsk,
        configuration.Configuration,
        configuration.ConfigurationDefaultCostPriceMethod,
        module='product', type_='model')
    Pool.register(
        product.ProductReplace,
        module='product', type_='wizard')
