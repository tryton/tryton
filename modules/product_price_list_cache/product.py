# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import json
from functools import partial

from sql import Null

from trytond.cache import Cache, freeze
from trytond.model import ModelSQL, dualmethod, fields
from trytond.pool import Pool, PoolMeta
from trytond.protocols.jsonrpc import JSONDecoder, JSONEncoder
from trytond.tools import grouped_slice, reduce_ids
from trytond.transaction import Transaction

dumps = partial(
    json.dumps, cls=JSONEncoder, separators=(',', ':'), sort_keys=True,
    ensure_ascii=False)
loads = partial(json.loads, object_hook=JSONDecoder())


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    cached_price_lists = fields.One2Many(
        'product.price_list.cache', 'product',
        "Cached Price Lists", readonly=True)


class PriceList(metaclass=PoolMeta):
    __name__ = 'product.price_list'

    @dualmethod
    def fill_cache(cls, price_lists=None, products=None):
        pool = Pool()
        Product = pool.get('product.product')
        Line = pool.get('product.price_list.line')
        Cache = pool.get('product.price_list.cache')
        line = Line.__table__()
        cursor = Transaction().connection.cursor()

        Cache.clear(price_lists=price_lists, products=products)

        if price_lists is None:
            price_lists = cls.search([])
        if products is None:
            products = Product.search([])

        cursor.execute(*line.select(
                line.quantity, distinct=True,
                where=line.quantity != Null))
        quantities = sorted({0} | {q for q, in cursor})

        for price_list in price_lists:
            caches = []
            with Transaction().set_context(Cache.context(price_list)):
                for product in Product.browse(products):
                    uom = price_list.get_uom(product)
                    for pattern in Cache.patterns(price_list, product):
                        unit_prices = []
                        for quantity in quantities:
                            unit_price = price_list.compute(
                                product, quantity, uom, pattern=pattern)
                            if (unit_prices
                                    and unit_prices[-1][1] == unit_price):
                                continue
                            else:
                                unit_prices.append((quantity, unit_price))
                        caches.append(Cache(
                                price_list=price_list,
                                product=product,
                                uom=uom,
                                raw_unit_prices=dumps(unit_prices),
                                pattern=pattern))
            Cache.save(caches)

    def compute(self, product, quantity, uom, pattern=None):
        pool = Pool()
        Cache = pool.get('product.price_list.cache')
        cache = Cache.get(self, product, pattern=pattern)
        unit_price = None
        if cache:
            unit_price = cache.get_unit_price(quantity, uom)
        if unit_price is None:
            unit_price = super().compute(
                product, quantity, uom, pattern=pattern)
        return unit_price


class PriceListCache(ModelSQL):
    __name__ = 'product.price_list.cache'

    price_list = fields.Many2One(
        'product.price_list', "Price List", required=True, ondelete='CASCADE')
    product = fields.Many2One(
        'product.product', "Product", required=True, ondelete='CASCADE')
    uom = fields.Many2One(
        'product.uom', "UoM", required=True, ondelete='CASCADE',
        help="The Unit of Measure.")
    raw_unit_prices = fields.Char("Unit Prices")
    pattern = fields.Dict(None, "Pattern")

    _get_cache = Cache('product.price_list.cache.get', context=False)
    _unit_prices_cache = Cache(
        'product.price_list.cache.unit_prices', context=False)

    @classmethod
    def context(cls, price_list):
        return {
            'company': price_list.company.id,
            }

    @classmethod
    def patterns(cls, price_list, product):
        yield None

    @property
    def unit_prices(self):
        unit_prices = self._unit_prices_cache.get(self.raw_unit_prices)
        if unit_prices is None:
            unit_prices = loads(self.raw_unit_prices)
            self._unit_prices_cache.set(self.raw_unit_prices, unit_prices)
        return unit_prices

    @classmethod
    def get(cls, price_list, product, pattern=None):
        if not price_list or not product:
            return
        if not pattern:
            pattern = None
        key = (price_list.id, product.id, freeze(pattern))
        try:
            cache_id, uom, raw_unit_prices = cls._get_cache.get(key)
        except TypeError:
            for cache in product.cached_price_lists:
                if (cache.price_list == price_list
                        and cache.pattern == pattern):
                    cls._get_cache.set(
                        key, (cache.id, cache.uom.id, cache.raw_unit_prices))
                    return cache
        else:
            return cls(cache_id, uom=uom, raw_unit_prices=raw_unit_prices)

    def get_unit_price(self, quantity, uom):
        pool = Pool()
        UoM = pool.get('product.uom')
        quantity = UoM.compute_qty(uom, quantity, self.uom)
        quantity = abs(quantity)
        unit_price = None
        for qty, cur_unit_price in self.unit_prices:
            if qty > quantity:
                return unit_price
            unit_price = cur_unit_price
        return unit_price

    @classmethod
    def clear(cls, price_lists=None, products=None):
        cache = cls.__table__()
        cursor = Transaction().connection.cursor()
        cls._get_cache.clear()

        if price_lists is None and products is None:
            cursor.execute(*cache.delete())
        elif price_lists and products is None:
            for sub_price_lists in grouped_slice(price_lists):
                cursor.execute(*cache.delete(where=reduce_ids(
                            cache.price_list, [
                                p.id for p in sub_price_lists])))
        elif price_lists is None and products:
            for sub_products in grouped_slice(products):
                cursor.execute(*cache.delete(where=reduce_ids(
                            cache.product, [p.id for p in sub_products])))
        else:
            for sub_products in grouped_slice(products):
                for sub_price_lists in grouped_slice(price_lists):
                    cursor.execute(*cache.delete(where=reduce_ids(
                            cache.price_list, [
                                p.id for p in sub_price_lists])
                            & reduce_ids(
                                cache.product, [p.id for p in sub_products])))

    @classmethod
    def on_modification(cls, mode, records, field_names=None):
        super().on_modification(mode, records, field_names=field_names)
        cls._get_cache.clear()
