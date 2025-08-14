# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt
import urllib.parse
from collections import defaultdict
from decimal import Decimal
from itertools import groupby
from operator import attrgetter

import shopify
from shopify.api_version import ApiVersion

import trytond.config as config
from trytond.cache import Cache
from trytond.i18n import gettext
from trytond.model import (
    MatchMixin, ModelSQL, ModelView, Unique, fields, sequence_ordered)
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.tools import grouped_slice
from trytond.transaction import Transaction
from trytond.url import http_host

from . import graphql
from .common import IdentifierMixin, IdentifiersMixin, gid2id, id2gid
from .exceptions import ShopifyCredentialWarning, ShopifyError
from .product import QUERY_PRODUCT
from .shopify_retry import GraphQLException

EDIT_ORDER_DELAY = dt.timedelta(days=60 + 1)


QUERY_SHOP = '''{
    shop %(fields)s
}'''


QUERY_SHOP_LOCALES = '''{
    shopLocales %(fields)s
}'''

QUERY_LOCATIONS = '''
query GetLocations($cursor: String) {
    locations(
        first: 250, includeInactive: true, includeLegacy: true,
        after: $cursor) {
        nodes {
            id
            name
        }
        pageInfo {
            hasNextPage
            endCursor
        }
    }
}'''


MUTATION_PRODUCT_SET = '''\
mutation productSet($input: ProductSetInput!) {
    productSet(input: $input) {
        product %(fields)s,
        userErrors {
            field
            message
        }
    }
}'''


QUERY_PRODUCT_CURSOR = '''\
query GetProduct($id: ID!, $cursor: String) {
    product(id: $id) %(fields)s
}'''


MUTATION_PRODUCT_CHANGE_STATUS = '''\
mutation productChangeStatus($productId: ID!, $status: ProductStatus!) {
    productChangeStatus(productId: $productId, status: $status) {
        userErrors {
            field
            message
        }
    }
}'''

MUTATION_INVENTORY_ITEM_UPDATE = '''\
mutation inventoryItemUpdate($id: ID!, $input: InventoryItemInput!) {
    inventoryItemUpdate(id: $id, input: $input) {
        InventoryItem %(fields)s,
        userErrors {
            field
            message
        }
    }
}'''


MUTATION_INVENTORY_ACTIVATE = '''\
mutation ActivateInventoryItem($inventoryItemId: ID!, $locationId: ID!) {
    inventoryActivate(
            inventoryItemId: $inventoryItemId, locationId: $locationId) {
        userErrors {
            field
            message
        }
    }
}'''


MUTATION_INVENTORY_SET_QUANTITIES = '''\
mutation InventorySet($input: InventorySetQuantitiesInput!) {
    inventorySetQuantities(input: $input) {
        userErrors {
            field
            message
        }
    }
}'''


MUTATION_COLLECTION_CREATE = '''\
mutation createCollection($input: CollectionInput!) {
    collectionCreate(input: $input) {
        collection %(fields)s,
        userErrors {
            field
            message
        }
    }
}'''

MUTATION_COLLECTION_UPDATE = '''\
mutation updateCollection($input: CollectionInput!) {
    collectionUpdate(input: $input) {
        collection %(fields)s,
        userErrors {
            field
            message
        }
    }
}'''

MUTATION_COLLECTION_DELETE = '''\
mutation collectionDelete($input: CollectionDeleteInput!) {
    collectionDelete(input: $input) {
        userErrors {
            field
            message
        }
    }
}'''


QUERY_ORDERS = '''\
query GetOrders {
    orders(first: 20, query: "%(query)s", sortKey: ID) %(fields)s
}'''


class Shop(metaclass=PoolMeta):
    __name__ = 'web.shop'

    _states = {
        'required': Eval('type') == 'shopify',
        'invisible': Eval('type') != 'shopify',
        }

    shopify_url = fields.Char("Shop URL", states=_states)
    shopify_version = fields.Selection(
        'get_shopify_versions', "Version", states=_states)
    shopify_password = fields.Char("Access Token", states=_states, strip=False)
    shopify_webhook_shared_secret = fields.Char(
        "Webhook Shared Secret", strip=False,
        states={
            'invisible': _states['invisible'],
            })
    shopify_webhook_endpoint_order = fields.Function(
        fields.Char(
            "Webhook Order Endpoint",
            help="The URL to be called by Shopify for Order events."),
        'on_change_with_shopify_webhook_endpoint_order')
    shopify_warehouses = fields.One2Many(
        'web.shop-stock.location', 'shop', "Warehouses", states=_states)
    shopify_payment_journals = fields.One2Many(
        'web.shop.shopify_payment_journal', 'shop', "Payment Journals",
        states=_states)
    shopify_fulfillment_notify_customer = fields.Boolean(
        "Notify Customer about Fulfillment",
        states={
            'invisible': Eval('type') != 'shopify',
            })

    del _states

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.type.selection.append(('shopify', "Shopify"))
        invisible = Eval('type') == 'shopify'
        for field in [cls.attributes, cls.attributes_removed, cls.warehouses]:
            if field.states.get('invisible'):
                field.states['invisible'] |= invisible
            else:
                field.states['invisible'] = invisible

    @classmethod
    def get_shopify_versions(cls):
        return [(None, "")] + sorted(
            ((v, v) for v in ApiVersion.versions), reverse=True)

    @fields.depends('name')
    def on_change_with_shopify_webhook_endpoint_order(self, name=None):
        if not self.name:
            return
        url_part = {
            'database_name': Transaction().database.name,
            'shop': self.name,
            }
        return http_host() + (
            urllib.parse.quote(
                '/%(database_name)s/web_shop_shopify/webhook/%(shop)s/order' %
                url_part))

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('//page[@id="shopify"]', 'states', {
                    'invisible': Eval('type') != 'shopify',
                    }),
            ]

    @classmethod
    def validate_fields(cls, shops, field_names):
        super().validate_fields(shops, field_names)
        if field_names & {'type', 'products'}:
            for shop in shops:
                if shop.type == 'shopify':
                    for product in shop.products:
                        shop._shopify_check_product(product)

    def _shopify_check_product(self, product):
        if not product.template.shopify_uom:
            shopify_uom = product.template.get_shopify_uom()
            if shopify_uom.digits:
                raise ShopifyError(gettext(
                        'web_shop_shopify.'
                        'msg_product_shopify_uom_digits',
                        product=product.rec_name))

    @property
    def to_sync(self):
        result = super().to_sync
        if self.type == 'shopify':
            result = True
        return result

    def get_sale(self, party=None):
        sale = super().get_sale(party=party)
        if self.type == 'shopify':
            sale.invoice_method = 'shipment'
        return sale

    def update_sales(self, sales):
        super().update_sales(sales)
        if self.type == 'shopify':
            self._shopify_update_order(self, sales)

    def shopify_session(self):
        return shopify.Session.temp(
            self.shopify_url, self.shopify_version, self.shopify_password)

    def shopify_shop(self, fields):
        return shopify.GraphQL().execute(QUERY_SHOP % {
                'fields': graphql.selection(fields),
                })['data']['shop']

    def shopify_shop_locales(self, fields):
        return shopify.GraphQL().execute(
            QUERY_SHOP_LOCALES % {
                'fields': graphql.selection(fields),
                })['data']['shopLocales']

    def get_payment_journal(self, currency_code, pattern):
        for payment_journal in self.shopify_payment_journals:
            if (payment_journal.journal.currency.code == currency_code
                    and payment_journal.match(pattern)):
                return payment_journal.journal

    def managed_metafields(self):
        return set()

    @classmethod
    def shopify_update_product(
            cls, shops=None, shop_fields=None, shop_locales_fields=None):
        """Update Shopify Products

        The transaction is committed after the creation of each new resource.
        """
        pool = Pool()
        InventoryItem = pool.get('product.shopify_inventory_item')
        transaction = Transaction()
        if shops is None:
            shops = cls.search([
                    ('type', '=', 'shopify'),
                    ])
        shop_fields = graphql.deep_merge(shop_fields or {}, {
                'currencyCode': None,
                'taxesIncluded': None,
                'weightUnit': None
                })
        shop_locales_fields = graphql.deep_merge(shop_locales_fields or {}, {
                'locale': None,
                'primary': None,
                })
        for shop in shops:
            with shop.shopify_session():
                shopify_shop = shop.shopify_shop(shop_fields)
                shop_language = (
                    shop.language.code if shop.language
                    else transaction.language)
                categories = shop.get_categories()
                products, prices, taxes = shop.get_products(
                    key=lambda p: p.template.id)
                sale_prices, sale_taxes = prices, taxes

                context = shop.get_context()
                with Transaction().set_context(_non_sale_price=True):
                    sale_context = shop.get_context()
                    if context != sale_context:
                        _, prices, taxes = shop.get_products()

                if shopify_shop['currencyCode'] != shop.currency.code:
                    raise ShopifyError(gettext(
                            'web_shop_shopify.msg_shop_currency_different',
                            shop=shop.rec_name,
                            shop_currency=shop.currency.code,
                            shopify_currency=shopify_shop['currencyCode']))
                shop_locales = shop.shopify_shop_locales(shop_locales_fields)
                primary_locale = next(
                    filter(lambda l: l['primary'], shop_locales))
                if primary_locale['locale'] != shop_language:
                    raise ShopifyError(gettext(
                            'web_shop_shopify.msg_shop_locale_different',
                            shop=shop.rec_name,
                            shop_language=shop_language,
                            shopify_primary_locale=primary_locale['locale'],
                            ))

                for category in categories:
                    shop._shopify_update_collection(category)

                categories = set(categories)
                inventory_items = dict(
                    zip(products, InventoryItem.browse(products)))
                for template, t_products in groupby(
                        products, key=lambda p: p.template):
                    t_products = sorted(
                        t_products, key=template.products.index)
                    p_inventory_items = [
                        inventory_items[p] for p in t_products]
                    p_sale_prices = [sale_prices[p.id] for p in t_products]
                    p_sale_taxes = [sale_taxes[p.id] for p in t_products]
                    p_prices = [prices[p.id] for p in t_products]
                    p_taxes = [taxes[p.id] for p in t_products]
                    if shop._shopify_product_is_to_update(
                            template, t_products, p_sale_prices, p_sale_taxes,
                            p_prices, p_taxes):
                        shop._shopify_update_product(
                            shopify_shop, categories, template, t_products,
                            p_inventory_items, p_sale_prices, p_sale_taxes,
                            p_prices, p_taxes)
                        Transaction().commit()

                for category in shop.categories_removed:
                    shop._shopify_remove_collection(category)
                shop.categories_removed = []

                products = set(products)
                for product in shop.products_removed:
                    template = product.template
                    if set(template.products).isdisjoint(products):
                        shop._shopify_remove_product(template)
                    product.set_shopify_identifier(shop)
                shop.products_removed = []
        cls.save(shops)

    def _shopify_update_collection(self, category, collection_fields=None):
        if not category.is_shopify_to_update(self):
            return
        collection_fields = graphql.deep_merge(collection_fields or {}, {
                'id': None,
                })
        collection = category.get_shopify(self)
        if collection.get('id') is not None:
            MUTATION = MUTATION_COLLECTION_UPDATE
            output = 'collectionUpdate'
        else:
            MUTATION = MUTATION_COLLECTION_CREATE
            output = 'collectionCreate'
        try:
            result = shopify.GraphQL().execute(
                MUTATION % {
                    'fields': graphql.selection(collection_fields),
                    }, {
                    'input': collection,
                    })['data'][output]
            if errors := result.get('userErrors'):
                raise GraphQLException({'errors': errors})
            collection = result['collection']
        except GraphQLException as e:
            raise ShopifyError(gettext(
                    'web_shop_shopify.msg_custom_collection_fail',
                    category=category.rec_name,
                    error="\n".join(
                        err['message'] for err in e.errors))) from e
        identifier = category.set_shopify_identifier(
            self, gid2id(collection['id']))
        if identifier.to_update:
            identifier.to_update = False
            identifier.save()
        Transaction().commit()
        return collection

    def _shopify_remove_collection(self, category):
        shopify_id = category.get_shopify_identifier(self)
        if shopify_id:
            shopify_id = id2gid('Collection', shopify_id)
            try:
                result = shopify.GraphQL().execute(
                    MUTATION_COLLECTION_DELETE, {
                        'input': {
                            'id': shopify_id,
                            }
                        })['data']['collectionDelete']
                if errors := result.get('userErrors'):
                    raise GraphQLException({'errors': errors})
            except GraphQLException:
                pass
            category.set_shopify_identifier(self)

    def _shopify_product_is_to_update(
            self, template, products, sale_prices, sale_taxes, prices, taxes):
        return (
            template.is_shopify_to_update(self)
            or any(
                prod.is_shopify_to_update(
                    self, sale_price=s_p, sale_tax=s_t, price=p, tax=t)
                for prod, s_p, s_t, p, t in zip(
                    products, sale_prices, sale_taxes, prices, taxes))
            or any(
                prod in self.products_removed for prod in products))

    def _shopify_update_product(
            self, shopify_shop, categories, template, products,
            inventory_items, sale_prices, sale_taxes, prices, taxes,
            product_fields=None):
        pool = Pool()
        Identifier = pool.get('web.shop.shopify_identifier')

        if not template.shopify_uom:
            template.shopify_uom = template.get_shopify_uom()
            template.save()

        product_fields = graphql.deep_merge(product_fields or {}, {
                'id': None,
                'variants(first: 250)': {
                    'nodes': {
                        'id': None,
                        'inventoryItem': {
                            'id': None,
                            },
                        },
                    'pageInfo': {
                        'hasNextPage': None,
                        'endCursor': None,
                        },
                    },
                })

        shopify_product = template.get_shopify(self, categories)
        variants = []
        for position, (
            product, inventory_item,
            sale_price, sale_tax,
            price, tax) in enumerate(zip(
                    products, inventory_items,
                    sale_prices, sale_taxes,
                    prices, taxes),
                start=1):
            self._shopify_check_product(product)
            variant = product.get_shopify(
                self, sale_price, sale_tax, price, tax,
                shop_taxes_included=shopify_shop['taxesIncluded'])
            variant['inventoryItem'] = inventory_item.get_shopify(
                self, shop_weight_unit=shopify_shop['weightUnit'])
            variant['position'] = position
            variants.append(variant)
        shopify_product['variants'] = variants

        if len(variants) == 1 and not shopify_product.get('productOptions'):
            shopify_product.setdefault('productOptions', []).append({
                    'name': "Title",
                    'values': [
                        {'name': "Default Title"},
                        ],
                    })
            variant, = variants
            variant.setdefault('optionValues', []).append({
                    'optionName': "Title",
                    'name': "Default Title",
                    })

        data = {
            'input': shopify_product,
            }
        try:
            result = shopify.GraphQL().execute(
                MUTATION_PRODUCT_SET % {
                    'fields': graphql.selection(product_fields),
                    }, data)['data']['productSet']
            if errors := result.get('userErrors'):
                raise GraphQLException({'errors': errors})
            shopify_product = result['product']

            identifiers = []
            identifier = template.set_shopify_identifier(
                self, gid2id(shopify_product['id']))
            if identifier.to_update:
                identifier.to_update = False
                identifiers.append(identifier)

            shopify_variants = graphql.iterate(
                QUERY_PRODUCT_CURSOR % {
                    'fields': graphql.selection({
                            'variants(first: 250, after: $cursor)': (
                                product_fields['variants(first: 250)']),
                            }),
                    },
                {'id': shopify_product['id']}, 'product',
                'variants', shopify_product)

            for (product, inventory_item,
                sale_price, sale_tax,
                price, tax,
                shopify_variant) in zip(
                    products, inventory_items,
                    sale_prices, sale_taxes,
                    prices, taxes,
                    shopify_variants):
                identifier = product.set_shopify_identifier(
                    self, gid2id(shopify_variant['id']))
                update_extra = {
                    'sale_price': sale_price,
                    'sale_tax': sale_tax,
                    'price': price,
                    'tax': tax,
                    }
                if (identifier.to_update
                        or identifier.to_update_extra != update_extra):
                    identifier.to_update = False
                    identifier.to_update_extra = update_extra
                    identifiers.append(identifier)
                identifier = inventory_item.set_shopify_identifier(
                    self, gid2id(shopify_variant['inventoryItem']['id']))
                if identifier.to_update:
                    identifier.to_update = False
                    identifiers.append(identifier)
            Identifier.save(identifiers)
            return shopify_product
        except GraphQLException as e:
            raise ShopifyError(gettext(
                    'web_shop_shopify.msg_product_fail',
                    template=template.rec_name,
                    error="\n".join(
                        err['message'] for err in e.errors))) from e

    def _shopify_remove_product(self, template):
        shopify_id = template.get_shopify_identifier(self)
        if shopify_id:
            shopify_id = id2gid('Product', shopify_id)
            product = shopify.GraphQL().execute(
                QUERY_PRODUCT % {
                    'fields': graphql.selection({
                            'id': None,
                            }),
                    }, {'id': shopify_id})['data']['product']
            if product:
                try:
                    result = shopify.GraphQL().execute(
                        MUTATION_PRODUCT_CHANGE_STATUS, {
                            'productId': shopify_id,
                            'status': 'ARCHIVED',
                            })['data']['productChangeStatus']
                    if errors := result.get('userErrors'):
                        raise GraphQLException({'errors': errors})
                except GraphQLException as e:
                    raise ShopifyError(gettext(
                            'web_shop_shopify.msg_product_fail',
                            template=template.rec_name,
                            error="\n".join(
                                err['message'] for err in e.errors))) from e

    @classmethod
    def shopify_update_inventory(cls, shops=None):
        """Update Shopify Inventory"""
        pool = Pool()
        Product = pool.get('product.product')
        if shops is None:
            shops = cls.search([
                    ('type', '=', 'shopify'),
                    ])
        for shop in shops:
            for shop_warehouse in shop.shopify_warehouses:
                if not (location_id := shop_warehouse.shopify_id):
                    continue
                location_id = id2gid('Location', location_id)
                with Transaction().set_context(
                        shop.get_context(),
                        **shop_warehouse.get_shopify_inventory_context()):
                    products = Product.browse([
                            p for p in shop.products if p.shopify_uom])
                    with shop.shopify_session():
                        shop._shopify_update_inventory(products, location_id)

    def _shopify_update_inventory(self, products, location_id):
        pool = Pool()
        InventoryItem = pool.get('product.shopify_inventory_item')
        inventory_items = InventoryItem.browse(products)

        input = {
            'ignoreCompareQuantity': True,
            'name': 'available',
            'reason': 'other',
            }
        input['quantities'] = quantities = []

        def set_quantities():
            try:
                for quantity in quantities:
                    result = shopify.GraphQL().execute(
                        MUTATION_INVENTORY_ACTIVATE, {
                            'inventoryItemId': quantity['inventoryItemId'],
                            'locationId': quantity['locationId'],
                            })['data']['inventoryActivate']
                    if errors := result.get('userErrors'):
                        raise GraphQLException({'errors': errors})
                result = shopify.GraphQL().execute(
                    MUTATION_INVENTORY_SET_QUANTITIES, {
                        'input': input,
                        })['data']['inventorySetQuantities']
                if errors := result.get('userErrors'):
                    raise GraphQLException({'errors': errors})
            except GraphQLException as e:
                raise ShopifyError(gettext(
                        'web_shop_shopify.msg_inventory_set_fail',
                        error="\n".join(
                            err['message'] for err in e.errors))) from e
            quantities.clear()

        for product, inventory_item in zip(products, inventory_items):
            inventory_item_id = inventory_item.get_shopify_identifier(self)
            if inventory_item_id:
                inventory_item_id = id2gid('InventoryItem', inventory_item_id)
                quantity = {
                    'inventoryItemId': inventory_item_id,
                    'locationId': location_id,
                    'quantity': int(product.shopify_quantity),
                    }
                quantities.append(quantity)
            if len(quantities) >= 250:
                set_quantities()
        if quantities:
            set_quantities()

    @classmethod
    def shopify_fetch_order(cls, shops=None):
        """Fetch new Shopify Order"""
        pool = Pool()
        Sale = pool.get('sale.sale')
        Payment = pool.get('account.payment')
        context = Transaction().context
        if shops is None:
            shops = cls.search([
                    ('type', '=', 'shopify'),
                    ])
        fields = {'nodes': Sale.shopify_fields()}
        cls.lock(shops)
        for shop in shops:
            last_sales = Sale.search([
                    ('web_shop', '=', shop.id),
                    ], order=[('shopify_identifier_signed', 'DESC')], limit=1)
            if last_sales:
                last_sale, = last_sales
                last_order_id = last_sale.shopify_identifier
            else:
                last_order_id = ''
            with shop.shopify_session():
                if pool.test and 'shopify_orders' in context:
                    query = ' OR '.join(
                        f'id:{id}' for id in context['shopify_orders'])
                elif last_order_id:
                    query = f'status:open AND id:>{last_order_id}'
                else:
                    query = 'status:open'
                orders = shopify.GraphQL().execute(
                    QUERY_ORDERS % {
                        'query': query,
                        'fields': graphql.selection(fields),
                        })['data']['orders']
                sales = []
                for order in orders['nodes']:
                    sales.append(Sale.get_from_shopify(shop, order))
                Sale.save(sales)
                for sale, order in zip(sales, orders['nodes']):
                    total_price = Decimal(
                        order['currentTotalPriceSet']['presentmentMoney'][
                            'amount'])
                    sale.shopify_tax_adjustment = (
                        total_price - sale.total_amount)
                Sale.save(sales)
                to_quote = [
                    s for s in sales if s.party != s.web_shop.guest_party]
                if to_quote:
                    Sale.quote(to_quote)
                for sale, order in zip(sales, orders['nodes']):
                    if sale.state != 'draft':
                        Payment.get_from_shopify(sale, order)
                Sale.payment_confirm(sales)

    @classmethod
    def shopify_update_order(cls, shops=None):
        """Update existing sale from Shopify"""
        pool = Pool()
        Sale = pool.get('sale.sale')
        if shops is None:
            shops = cls.search([
                    ('type', '=', 'shopify'),
                    ])
        now = dt.datetime.now()
        for shop in shops:
            sales = Sale.search([
                    ('web_shop', '=', shop.id),
                    ('shopify_identifier', '!=', None),
                    ['OR',
                        ('state', 'in',
                            ['quotation', 'confirmed', 'processing']),
                        ('create_date', '>=', now - EDIT_ORDER_DELAY),
                        ],
                    ])
            for sub_sales in grouped_slice(sales, count=20):
                cls._shopify_update_order(shop, list(sub_sales))
                cls.__queue__._shopify_update_order(
                    shop, [s.id for s in sub_sales])

    @classmethod
    def _shopify_update_order(cls, shop, sales):
        pool = Pool()
        Sale = pool.get('sale.sale')
        sales = Sale.browse(sales)
        assert shop.type == 'shopify'
        assert all(s.web_shop == shop for s in sales)
        fields = {'nodes': Sale.shopify_fields()}
        with shop.shopify_session():
            query = ' OR '.join(
                f'id:{s.shopify_identifier}' for s in sales)
            orders = shopify.GraphQL().execute(
                QUERY_ORDERS % {
                    'query': query,
                    'fields': graphql.selection(fields),
                    })['data']['orders']
            id2order = {gid2id(o['id']): o for o in orders['nodes']}

        to_update = []
        orders = []
        for sale in sales:
            try:
                order = id2order[sale.shopify_identifier]
            except KeyError:
                continue
            to_update.append(sale)
            orders.append(order)
        cls.shopify_update_sale(to_update, orders)

    @classmethod
    def shopify_update_sale(cls, sales, orders):
        """Update sales based on Shopify orders"""
        pool = Pool()
        Amendment = pool.get('sale.amendment')
        Payment = pool.get('account.payment')
        Sale = pool.get('sale.sale')
        assert len(sales) == len(orders)
        to_update = {}
        states_to_restore = defaultdict(list)
        for sale, order in zip(sales, orders):
            assert sale.shopify_identifier == gid2id(order['id'])
            shop = sale.web_shop
            with shop.shopify_session():
                sale = Sale.get_from_shopify(shop, order, sale=sale)
                if sale._changed_values():
                    sale.untaxed_amount_cache = None
                    sale.tax_amount_cache = None
                    sale.total_amount_cache = None
                    sale.shopify_tax_adjustment = None
                    to_update[sale] = order
                    states_to_restore[sale.state].append(sale)
        Sale.write(list(to_update.keys()), {'state': 'draft'})
        Sale.save(to_update.keys())
        for state, state_sales in states_to_restore.items():
            Sale.write(list(state_sales), {'state': state})
        for sale, order in to_update.items():
            current_total_price = Decimal(
                order['currentTotalPriceSet']['presentmentMoney']['amount'])
            sale.shopify_tax_adjustment = (
                current_total_price - sale.total_amount)
        Sale.save(to_update.keys())
        Sale.store_cache(to_update.keys())
        Amendment._clear_sale(to_update.keys())
        to_process, to_quote = [], []
        for sale in to_update:
            if sale.party == sale.web_shop.guest_party:
                continue
            if sale.payment_amount_authorized >= sale.amount_to_pay:
                to_process.append(sale)
            else:
                to_quote.append(sale)
        if to_process:
            Sale.__queue__.process(to_process)
        if to_quote:
            # Use write because there is no transition
            Sale.write(to_quote, {'state': 'quotation'})
            cls.log(to_quote, 'transition', 'state:quotation')

        for sale, order in zip(sales, orders):
            if sale.state != 'draft':
                shop = sale.web_shop
                with shop.shopify_session():
                    Payment.get_from_shopify(sale, order)
        Sale.payment_confirm(sales)

    @classmethod
    def check_modification(cls, mode, shops, values=None, external=False):
        pool = Pool()
        Warning = pool.get('res.user.warning')
        super().check_modification(
            mode, shops, values=values, external=external)
        if (mode == 'write'
                and external
                and values.keys() & {
                    'shopify_url', 'shopify_password',
                    'shopify_webhook_shared_secret'}):
            warning_name = Warning.format('shopify_credential', shops)
            if Warning.check(warning_name):
                raise ShopifyCredentialWarning(
                    warning_name,
                    gettext('web_shop_shopify'
                        '.msg_shopidy_credential_modified'))


class Shop_Image(metaclass=PoolMeta):
    __name__ = 'web.shop'

    def _shopify_product_is_to_update(
            self, template, products, sale_prices, sale_taxes, prices, taxes):
        return (
            super()._shopify_product_is_to_update(
                template, products, sale_prices, sale_taxes, prices, taxes)
            or any(
                i.is_shopify_to_update(self) for i in template.shopify_images))

    def _shopify_update_product(
            self, shopify_shop, categories, template, products,
            inventory_items, sale_prices, sale_taxes, prices, taxes,
            product_fields=None):
        pool = Pool()
        Identifier = pool.get('web.shop.shopify_identifier')

        product_fields = (
            product_fields.copy() if product_fields is not None else {})
        product_fields = graphql.deep_merge(product_fields or {}, {
                'media(first: 250)': {
                    'nodes': {
                        'id': None,
                        'mediaContentType': None,
                        },
                    'pageInfo': {
                        'hasNextPage': None,
                        'endCursor': None,
                        },
                    },
                })
        shopify_product = super()._shopify_update_product(
            shopify_shop, categories, template, products, inventory_items,
            sale_prices, sale_taxes, prices, taxes,
            product_fields=product_fields)

        try:
            shopify_media = graphql.iterate(
                QUERY_PRODUCT_CURSOR % {
                    'fields': graphql.selection({
                            'media(first: 250, after: $cursor)': (
                                product_fields['media(first: 250)']),
                            }),
                    },
                {'id': shopify_product['id']}, 'product',
                'media', shopify_product)

            identifiers = []
            for image, shopify_image in zip(
                    template.shopify_images,
                    filter(lambda m: m['mediaContentType'] == 'IMAGE',
                        shopify_media)):
                identifier = image.set_shopify_identifier(
                    self, gid2id(shopify_image['id']))
                if identifier.to_update:
                    identifier.to_update = False
                    identifiers.append(identifier)
            Identifier.save(identifiers)
            return shopify_product
        except GraphQLException as e:
            raise ShopifyError(gettext(
                    'web_shop_shopify.msg_product_fail',
                    template=template.rec_name,
                    error="\n".join(
                        err['message'] for err in e.errors))) from e


class ShopShopifyIdentifier(IdentifierMixin, ModelSQL, ModelView):
    __name__ = 'web.shop.shopify_identifier'

    record = fields.Reference("Record", 'get_records', required=True)
    web_shop = fields.Many2One(
        'web.shop', "Web Shop", required=True, ondelete='CASCADE')
    to_update = fields.Boolean("To Update")
    to_update_extra = fields.Dict(None, "To Update Extra")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.shopify_identifier_signed.states = {
            'required': True,
            }
        t = cls.__table__()
        cls._sql_constraints += [
            ('web_shop_record_unique',
                Unique(t, t.record, t.web_shop),
                'web_shop_shopify.msg_identifier_record_web_shop_unique'),
            ]
        cls._buttons.update({
                'set_to_update': {},
                })

    @classmethod
    def __register__(cls, module):
        table_h = cls.__table_handler__(module)
        super().__register__(module)
        # Migration from 7.6: replace record_web_shop_unique
        table_h.drop_constraint('record_web_shop_unique')

    @classmethod
    def get_records(cls):
        pool = Pool()
        Model = pool.get('ir.model')
        get_name = Model.get_name
        models = (klass.__name__ for _, klass in pool.iterobject()
            if issubclass(klass, IdentifiersMixin))
        return [(m, get_name(m)) for m in models]

    @classmethod
    def set_to_update(cls, identifiers):
        cls.write(identifiers, {'to_update': True})

    @property
    def shopify_resource(self):
        if self.record.__name__ == 'product.product':
            product_identifier = self.record.template.get_shopify_identifier(
                self.web_shop)
            resource = f'products/{product_identifier}/variants'
        else:
            resource = {
                'party.party': 'customers',
                'product.category': 'collections',
                'product.template': 'products',
                }.get(self.record.__name__)
        return resource


class Shop_Warehouse(ModelView, metaclass=PoolMeta):
    __name__ = 'web.shop-stock.location'

    shopify_stock_skip_warehouse = fields.Boolean(
        "Only storage zone",
        help="Check to use only the quantity of the storage zone.")
    shopify_id = fields.Selection(
        'get_shopify_locations', "Shopify ID")
    _shopify_locations_cache = Cache(
        __name__ + '.get_shopify_locations',
        duration=config.getint(
            'web_shop_shopify', 'locations_cache', default=15 * 60),
        context=False)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('shop')
        t = cls.__table__()
        cls._sql_constraints += [
            ('shopify_id_unique',
                Unique(t, t.shopify_id),
                'web_shop_shopify.msg_location_id_unique'),
            ]

    @fields.depends(
        'shop', '_parent_shop.shopify_url', '_parent_shop.shopify_version',
        '_parent_shop.shopify_password')
    def get_shopify_locations(self):
        locations = [(None, "")]
        session = attrgetter(
            'shopify_url', 'shopify_version', 'shopify_password')
        if self.shop and all(session(self.shop)):
            locations_cache = self._shopify_locations_cache.get(self.shop.id)
            if locations_cache is not None:
                return locations_cache
            try:
                with self.shop.shopify_session():
                    for location in graphql.iterate(
                            QUERY_LOCATIONS, {}, 'locations'):
                        locations.append(
                            (str(gid2id(location['id'])), location['name']))
                self._shopify_locations_cache.set(self.shop.id, locations)
            except GraphQLException:
                pass
        return locations

    def get_shopify_inventory_context(self):
        return {
            'locations': [self.warehouse.id],
            'stock_skip_warehouse': self.shopify_stock_skip_warehouse,
            'with_childs': True,
            }


class Shop_Attribute(metaclass=PoolMeta):
    __name__ = 'web.shop-product.attribute'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        domain = [
            ('type', '!=', 'shopify'),
            ]
        if cls.shop.domain:
            cls.shop.domain = [cls.shop.domain, domain]
        else:
            cls.shop.domain = domain


class ShopShopifyPaymentJournal(
        sequence_ordered(), MatchMixin, ModelSQL, ModelView):
    __name__ = 'web.shop.shopify_payment_journal'

    shop = fields.Many2One(
        'web.shop', "Shop", required=True, ondelete='CASCADE',
        domain=[
            ('type', '=', 'shopify'),
            ])
    gateway = fields.Char(
        "Gateway",
        help="The payment gateway name for which the journal must be used.")
    journal = fields.Many2One(
        'account.payment.journal', "Journal", required=True,
        domain=[
            ('process_method', '=', 'shopify'),
            ])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('shop')

# TODO: add wizard to export translations
