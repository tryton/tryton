# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import re

from trytond.model import MatchMixin, ModelSQL, ModelView, fields
from trytond.pool import PoolMeta


class Carrier(metaclass=PoolMeta):
    __name__ = 'carrier'

    shopify_selections = fields.One2Many(
        'carrier.selection.shopify', 'carrier', "Shopify Selections",
        help="Define the criteria that will match this carrier "
        "with the Shopify shipping methods.")

    def shopify_match(self, shop, shipping_line, pattern=None):
        pattern = pattern.copy() if pattern is not None else {}
        pattern.setdefault('shop', shop.id)
        pattern.setdefault('code', shipping_line.get('code'))
        pattern.setdefault('title', shipping_line.get('title'))
        for selection in self.shopify_selections:
            if selection.match(pattern):
                return True
        return False


class SelectionShopify(MatchMixin, ModelSQL, ModelView):
    __name__ = 'carrier.selection.shopify'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('carrier')

    carrier = fields.Many2One(
        'carrier', "Carrier", required=True, ondelete='CASCADE')
    shop = fields.Many2One(
        'web.shop', "Shop",
        domain=[
            ('type', '=', 'shopify'),
            ])
    code = fields.Char(
        "Code",
        help="The code of the shipping line.")
    title = fields.Char(
        "Title",
        help="A regular expression to match the shipping line title.\n"
        "Leave empty to allow any title.")

    def match(self, pattern, match_none=False):
        if 'title' in pattern:
            pattern = pattern.copy()
            title = pattern.pop('title') or ''
            if (self.title is not None
                    and not re.search(self.title, title, flags=re.I)):
                return False
        return super().match(pattern, match_none=match_none)
