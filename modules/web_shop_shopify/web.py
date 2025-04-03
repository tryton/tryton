# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt
import urllib.parse
from decimal import Decimal
from operator import attrgetter

import pyactiveresource
import shopify
from shopify.api_version import ApiVersion

from trytond.cache import Cache
from trytond.config import config
from trytond.i18n import gettext
from trytond.model import (
    MatchMixin, ModelSQL, ModelView, Unique, fields, sequence_ordered)
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.tools import grouped_slice
from trytond.transaction import Transaction
from trytond.url import http_host

from .common import IdentifierMixin, IdentifiersMixin
from .exceptions import ShopifyCredentialWarning, ShopifyError

EDIT_ORDER_DELAY = dt.timedelta(days=60 + 1)


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

    def shopify_session(self):
        return shopify.Session.temp(
            self.shopify_url, self.shopify_version, self.shopify_password)

    def get_payment_journal(self, currency_code, pattern):
        for payment_journal in self.shopify_payment_journals:
            if (payment_journal.journal.currency.code == currency_code
                    and payment_journal.match(pattern)):
                return payment_journal.journal

    def managed_metafields(self):
        return set()

    def __sync_metafields(self, resource, metafields):
        metafields = metafields.copy()
        managed_metafields = self.managed_metafields()
        assert metafields.keys() <= managed_metafields
        for metafield in resource.metafields():
            key = '.'.join([metafield.namespace, metafield.key])
            value = metafield.to_dict()
            if key not in metafields:
                if key in managed_metafields:
                    metafield.destroy()
            elif metafields[key] != value:
                for k, v in metafields.pop(key).items():
                    setattr(metafield, k, v)
                metafield.save()
        for key, value in metafields.items():
            namespace, key = key.split('.', 1)
            value['namespace'] = namespace
            value['key'] = key
            resource.add_metafield(shopify.Metafield(value))

    @classmethod
    def shopify_update_product(cls, shops=None):
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
        for shop in shops:
            with shop.shopify_session():
                shopify_shop = shopify.Shop.current()
                shop_language = (
                    shop.language.code if shop.language
                    else transaction.language)
                categories = shop.get_categories()
                products, prices, taxes = shop.get_products()
                if shopify_shop.currency.lower() != shop.currency.code.lower():
                    raise ShopifyError(gettext(
                            'web_shop_shopify.msg_shop_currency_different',
                            shop=shop.rec_name,
                            shop_currency=shop.currency.code,
                            shopify_currency=shopify_shop.currency))
                if (shopify_shop.primary_locale.lower()
                        != shop_language.lower()):
                    raise ShopifyError(gettext(
                            'web_shop_shopify.msg_shop_locale_different',
                            shop=shop.rec_name,
                            shop_language=shop_language,
                            shopify_primary_locale=shopify_shop.primary_locale
                            ))

                for category in categories:
                    shop.__shopify_update_category(category)

                categories = set(categories)
                inventory_items = InventoryItem.browse(products)
                for product, inventory_item in zip(products, inventory_items):
                    price = prices[product.id]
                    tax = taxes[product.id]

                    template = product.template
                    if not template.shopify_uom:
                        shop._shopify_check_product(product)
                        template.shopify_uom = template.get_shopify_uom()
                        template.save()

                    shop.__shopify_update_template(
                        shopify_shop, categories, template,
                        product, price, tax)
                    shop.__shopify_update_product(
                        shopify_shop, product, price, tax)
                    shop.__shopify_update_inventory_item(inventory_item)

                for category in shop.categories_removed:
                    shop.__shopify_remove_category(category)
                shop.categories_removed = []

                products = set(products)
                for product in shop.products_removed:
                    template = product.template
                    if set(template.products).isdisjoint(products):
                        shop.__shopify_remove_template(template)
                    else:
                        shop.__shopify_remove_product(product)
                shop.products_removed = []
        cls.save(shops)

    def __shopify_update_category(self, category):
        if not category.is_shopify_to_update(self):
            return
        custom_collection = category.get_shopify(self)
        if not custom_collection.save():
            raise ShopifyError(gettext(
                    'web_shop_shopify.msg_custom_collection_fail',
                    category=category.rec_name,
                    error="\n".join(
                        custom_collection.errors.full_messages())))
        identifier = category.set_shopify_identifier(
            self, custom_collection.id)
        if identifier.to_update:
            identifier.to_update = False
            identifier.save()
        Transaction().commit()

        self.__sync_metafields(
            custom_collection, category.get_shopify_metafields(self))

    def __shopify_remove_category(self, category):
        shopify_id = category.get_shopify_identifier(self)
        if shopify_id:
            if shopify.CustomCollection.exists(shopify_id):
                shopify.CustomCollection.find(shopify_id).destroy()
            category.set_shopify_identifier(self)

    def __shopify_update_template(
            self, shopify_shop, categories, template, product, price, tax):
        if not template.is_shopify_to_update(self):
            return
        shopify_product = template.get_shopify(self)
        new = shopify_product.is_new()
        if new:
            shopify_product.variants = [
                product.get_shopify(
                    self, price, tax,
                    shop_taxes_included=shopify_shop.taxes_included,
                    shop_weight_unit=shopify_shop.weight_unit)]
        else:
            # Set fake value for missing new options
            for j, variant in enumerate(shopify_product.variants):
                for i, _ in range(len(shopify_product.options), 1):
                    name = 'option%i' % i
                    if not getattr(variant, name, None):
                        setattr(variant, name, '_option%i-%i' % (i, j))
        if not shopify_product.save():
            raise ShopifyError(gettext(
                    'web_shop_shopify.msg_product_fail',
                    template=template.rec_name,
                    error="\n".join(shopify_product.errors.full_messages())))
        identifier = template.set_shopify_identifier(
            self, shopify_product.id)
        if identifier.to_update:
            identifier.to_update = False
            identifier.save()
        if new:
            variant, = shopify_product.variants
            product.set_shopify_identifier(self, variant.id)
        Transaction().commit()

        self.__sync_metafields(
            shopify_product, template.get_shopify_metafields(self))

        collection_ids = {
            c.id for c in shopify_product.collections()}
        for category in template.categories_all:
            while category:
                if category in categories:
                    custom_collection = (
                        shopify.CustomCollection.find(
                            category.get_shopify_identifier(
                                self)))
                    if custom_collection.id in collection_ids:
                        collection_ids.remove(
                            custom_collection.id)
                    else:
                        shopify_product.add_to_collection(
                            custom_collection)
                category = category.parent
        for collection_id in collection_ids:
            collection = shopify.CustomCollection.find(
                collection_id)
            shopify_product.remove_from_collection(collection)

        self.__shopify_update_images(template, shopify_product)

    def __shopify_remove_template(self, template):
        shopify_id = template.get_shopify_identifier(self)
        if not shopify_id:
            return
        if shopify.Product.exists(shopify_id):
            shopify.Product.find(shopify_id).destroy()
        template.set_shopify_identifier(self)
        for product in template.products:
            product.set_shopify_identifier(self)
        if getattr(template, 'images', None):
            for image in template.images:
                image.set_shopify_identifier(self)

    def __shopify_update_images(self, template, shopify_product):
        if not getattr(template, 'images', None):
            return
        transaction = Transaction()
        image_ids = set()
        for i, image in enumerate(filter(
                    lambda i: i.web_shop,
                    template.images_used), 1):
            product_image = image.get_shopify(self)
            new_image = not product_image.id
            product_image.position = i
            if not product_image.save():
                raise ShopifyError(gettext(
                        'web_shop_shopify'
                        '.msg_product_image_fail',
                        image=image.rec_name,
                        template=template.rec_name,
                        error="\n".join(
                            product_image.errors
                            .full_messages())))
            image_ids.add(product_image.id)
            if new_image:
                image.set_shopify_identifier(
                    self, product_image.id)
                transaction.commit()

        for image in shopify_product.images:
            if image.id not in image_ids:
                image.destroy()

    def __shopify_update_product(self, shopify_shop, product, price, tax):
        update_extra = {'price': str(price), 'tax': str(tax)}
        if not product.is_shopify_to_update(self, **update_extra):
            return
        variant = product.get_shopify(
            self, price, tax,
            shop_taxes_included=shopify_shop.taxes_included,
            shop_weight_unit=shopify_shop.weight_unit)
        if not variant.save():
            raise ShopifyError(gettext(
                    'web_shop_shopify.msg_variant_fail',
                    product=product.rec_name,
                    error="\n".join(variant.errors.full_messages())
                    ))
        identifier = product.set_shopify_identifier(self, variant.id)
        if identifier.to_update or identifier.to_update_extra != update_extra:
            identifier.to_update = False
            identifier.to_update_extra = update_extra
            identifier.save()
        Transaction().commit()

        self.__sync_metafields(variant, product.get_shopify_metafields(self))

    def __shopify_update_inventory_item(self, inventory_item):
        if not inventory_item.is_shopify_to_update(self):
            return
        shopify_inventory_item = inventory_item.get_shopify(self)
        if shopify_inventory_item:
            if not shopify_inventory_item.save():
                raise ShopifyError(gettext(
                        'web_shop_shopify.msg_inventory_item_fail',
                        product=inventory_item.product.rec_name,
                        error="\n".join(
                            inventory_item.errors.full_messages())))
            identifier = inventory_item.set_shopify_identifier(
                self, shopify_inventory_item.id if
                shopify_inventory_item.tracked else None)
            if identifier and identifier.to_update:
                identifier.to_update = False
                identifier.save()
            Transaction().commit()

    def __shopify_remove_product(self, product):
        shopify_id = product.get_shopify_identifier(self)
        if shopify_id:
            if shopify.Variant.exists(shopify_id):
                shopify.Variant.find(shopify_id).destroy()
            product.set_shopify_identifier(self)

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
                location_id = shop_warehouse.shopify_id
                if not location_id:
                    continue
                location_id = int(location_id)
                with Transaction().set_context(
                        shop.get_context(),
                        **shop_warehouse.get_shopify_inventory_context()):
                    products = Product.browse([
                            p for p in shop.products if p.shopify_uom])
                    with shop.shopify_session():
                        shop.__shopify_update_inventory(products, location_id)

    def __shopify_update_inventory(self, products, location_id):
        pool = Pool()
        InventoryItem = pool.get('product.shopify_inventory_item')
        inventory_items = InventoryItem.browse(products)
        product2quantity = {p.id: int(p.shopify_quantity) for p in products}
        shopify2product = {
            i.get_shopify_identifier(self): i.id for i in inventory_items}
        shopify2product.pop(None, None)
        product2shopify = {v: k for k, v in shopify2product.items()}

        location = shopify.Location.find(location_id)
        for i, inventory_level in enumerate(
                location.inventory_levels(limit=250, no_iter_next=False)):
            inventory_item_id = inventory_level.inventory_item_id
            product_id = shopify2product.get(inventory_item_id)
            if product_id is None:
                continue
            quantity = product2quantity.pop(product_id)
            if inventory_level.available != quantity:
                try:
                    shopify.InventoryLevel.set(
                        location_id, inventory_item_id, quantity)
                except pyactiveresource.connection.ResourceNotFound:
                    pass

        for product_id, quantity in product2quantity.items():
            inventory_item_id = product2shopify.get(product_id)
            if inventory_item_id is None:
                continue
            try:
                shopify.InventoryLevel.set(
                    location_id, inventory_item_id, quantity)
            except pyactiveresource.connection.ResourceNotFound:
                pass

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
                if 'shopify_orders' in context:
                    orders = shopify.Order.find(
                        ids=context['shopify_orders'],
                        limit=250, no_iter_next=False)
                else:
                    orders = shopify.Order.find(
                        status='open', since_id=last_order_id,
                        limit=250, no_iter_next=False)
                sales = []
                for i, order in enumerate(orders):
                    sales.append(Sale.get_from_shopify(shop, order))
                Sale.save(sales)
                for sale, order in zip(sales, orders):
                    sale.shopify_tax_adjustment = (
                        Decimal(order.total_price) - sale.total_amount)
                Sale.save(sales)
                Sale.quote(sales)
                for sale, order in zip(sales, orders):
                    Payment.get_from_shopify(sale, order)

    @classmethod
    def shopify_update_order(cls, shops=None):
        """Update existing sale from Shopify"""
        pool = Pool()
        Sale = pool.get('sale.sale')
        if shops is None:
            shops = cls.search([
                    ('type', '=', 'shopify'),
                    ])
        cls.lock(shops)
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
            for sub_sales in grouped_slice(sales, count=250):
                cls._shopify_update_order(shop, list(sub_sales))

    @classmethod
    def _shopify_update_order(cls, shop, sales):
        assert shop.type == 'shopify'
        assert all(s.web_shop == shop for s in sales)
        with shop.shopify_session():
            orders = shopify.Order.find(
                ids=','.join(str(s.shopify_identifier) for s in sales),
                status='any')
            id2order = {o.id: o for o in orders}

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
        for sale, order in zip(sales, orders):
            assert sale.shopify_identifier == order.id
            shop = sale.web_shop
            with shop.shopify_session():
                sale = Sale.get_from_shopify(shop, order, sale=sale)
                if sale._changed_values():
                    sale.untaxed_amount_cache = None
                    sale.tax_amount_cache = None
                    sale.total_amount_cache = None
                    to_update[sale] = order
                Payment.get_from_shopify(sale, order)
        Sale.save(to_update.keys())
        for sale, order in to_update.items():
            sale.shopify_tax_adjustment = (
                Decimal(order.current_total_price) - sale.total_amount)
        Sale.store_cache(to_update.keys())
        Amendment._clear_sale(to_update.keys())
        to_process, to_quote = [], []
        for sale in to_update:
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

    @classmethod
    def write(cls, *args):
        pool = Pool()
        Warning = pool.get('res.user.warning')
        actions = iter(args)
        for shops, values in zip(actions, actions):
            if ({'shopify_url', 'shopify_password',
                    'shopify_webhook_shared_secret'}
                    & values.keys()):
                warning_name = Warning.format('shopify_credential', shops)
                if Warning.check(warning_name):
                    raise ShopifyCredentialWarning(
                        warning_name,
                        gettext('web_shop_shopify'
                            '.msg_shopidy_credential_modified'))
        return super().write(*args)


class ShopShopifyIdentifier(IdentifierMixin, ModelSQL, ModelView):
    "Shopify Identifier"
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
            ('record_web_shop_unique',
                Unique(t, t.record, t.shopify_identifier_signed),
                'web_shop_shopify.msg_identifier_record_web_shop_unique'),
            ]
        cls._buttons.update({
                'set_to_update': {},
                })

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
                    locations += [
                        (str(l.id), l.name)
                        for l in shopify.Location.find(no_iter_next=False)]
                self._shopify_locations_cache.set(self.shop.id, locations)
            except (AttributeError,
                    shopify.VersionNotFoundError,
                    pyactiveresource.connection.Error):
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
    "Shopify Payment Journal"
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
