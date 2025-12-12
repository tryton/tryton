# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from sql import Literal

from trytond.pool import Pool


class AbstractMixin:
    __slots__ = ()

    @classmethod
    def _joins(cls):
        pool = Pool()
        Product = pool.get('product.product')
        Template = pool.get('product.template')
        from_item, tables, withs = super()._joins()
        if 'line.product' not in tables:
            product = Product.__table__()
            tables['line.product'] = product
            line = tables['line']
            from_item = (from_item
                .join(product, condition=line.product == product.id))
        else:
            product = tables['line.product']
        if 'line.product.template' not in tables:
            template = Template.__table__()
            tables['line.product.template'] = template
            from_item = (from_item
                .join(template, condition=product.template == template.id))
        return from_item, tables, withs

    @classmethod
    def _where(cls, tables, withs):
        template = tables['line.product.template']
        where = super()._where(tables, withs)
        where &= template.gift_card != Literal(True)
        return where
