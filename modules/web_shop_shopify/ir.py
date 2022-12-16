# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


class Cron(metaclass=PoolMeta):
    __name__ = 'ir.cron'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.method.selection.extend([
                ('web.shop|shopify_update_product', "Update Shopify Products"),
                ('web.shop|shopify_update_inventory',
                    "Update Shopify Inventory"),
                ('web.shop|shopify_fetch_order', "Fetch Shopify Orders"),
                ('web.shop|shopify_update_order', "Update Shopify Orders"),
                ])
