# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.i18n import gettext
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'

    supply_on_sale = fields.Boolean('Supply On Sale',
        states={
            'invisible': ~Eval('purchasable') | ~Eval('salable'),
            })

    @fields.depends(methods=['_notify_order_point'])
    def on_change_notify(self):
        notifications = super().on_change_notify()
        notifications.extend(self._notify_order_point())
        return notifications

    @fields.depends('id', 'supply_on_sale')
    def _notify_order_point(self):
        pool = Pool()
        try:
            OrderPoint = pool.get('stock.order_point')
        except KeyError:
            return
        if self.supply_on_sale and self.id is not None and self.id >= 0:
            order_points = OrderPoint.search([
                    ('product.template.id', '=', self.id),
                    ('type', '=', 'purchase'),
                    ], limit=6)
            if order_points:
                names = ', '.join(o.rec_name for o in order_points[:5])
                if len(order_points) > 5:
                    names + '...'
                yield ('warning', gettext(
                        'sale_supply'
                        '.msg_template_supply_on_sale_order_point',
                        order_points=names))


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'
