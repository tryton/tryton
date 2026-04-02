# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

__all__ = [
    'price_digits', 'round_price', 'uom_conversion_digits',
    'ProductDeactivatableMixin', 'TemplateDeactivatableMixin',
    'copy_template_filtered', 'copy_product_filtered']


def __getattr__(name):
    if name == 'uom_conversion_digits':
        from .uom import uom_conversion_digits
        return uom_conversion_digits
    elif name in {
            'price_digits', 'round_price',
            'ProductDeactivatableMixin', 'TemplateDeactivatableMixin',
            'copy_template_filtered', 'copy_product_filtered'}:
        from . import product
        return getattr(product, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
