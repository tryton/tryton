# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from functools import wraps

from elasticsearch import Elasticsearch, VERSION as ES_VERSION

from trytond.exceptions import RateLimitException
from trytond.i18n import lazy_gettext, gettext
from trytond.model import ModelSQL, Unique, fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from .exceptions import LoginException, NotFound, BadRequest


def migrate_doc_type(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if ES_VERSION >= (7,):
            kwargs = kwargs.copy()
            doc_type = kwargs.pop('doc_type')
            kwargs['index'] += '_' + doc_type
        return func(*args, **kwargs)
    return wrapper


class VSFElasticsearch(Elasticsearch):

    @migrate_doc_type
    def index(self, **kwargs):
        print(kwargs)
        return super().index(**kwargs)

    @migrate_doc_type
    def delete(self, **kwargs):
        return super().delete(**kwargs)


def join_name(firstname, lastname):
    # Use unbreakable spaces in firstname
    # to prevent to split on them
    firstname = firstname.replace(' ', ' ')
    return ' '.join([firstname, lastname])


def split_name(name):
    return (name.split(' ', 1) + [''])[:2]


def issubdict(dct, other):
    for key, value in dct.items():
        if value != other.get(key):
            return False
    return True


def with_user(required=False):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            pool = Pool()
            User = pool.get('web.user')
            token = kwargs.pop('token', None)
            if token:
                user = User.get_user(token)
            else:
                user = kwargs.get('user')
            if required and not user:
                raise LoginException()
            kwargs['user'] = user
            return func(*args, **kwargs)
        return wrapper
    return decorator


class Shop(metaclass=PoolMeta):
    __name__ = 'web.shop'

    vsf_elasticsearch_url = fields.Char(
        "Elasticsearch URL",
        states={
            'required': Eval('type') == 'vsf',
            'invisible': Eval('type') != 'vsf',
            },
        depends=['type'])
    vsf_elasticsearch_index = fields.Char(
        "Elasticsearch Index",
        states={
            'required': Eval('type') == 'vsf',
            'invisible': Eval('type') != 'vsf',
            },
        depends=['type'])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.type.selection.append(('vsf', "Vue Storefront"))

    @classmethod
    def default_vsf_elasticsearch_url(cls):
        return 'http://localhost:9200/'

    @classmethod
    def default_vsf_elasticsearch_index(cls):
        return 'vue_storefront_catalog'

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('//page[@id="vsf"]', 'states', {
                    'invisible': Eval('type') != 'vsf',
                    }),
            ]

    @property
    def to_sync(self):
        result = super().to_sync
        if self.type == 'vsf':
            result = True
        return result

    def get_vsf_elasticsearch(self):
        return VSFElasticsearch(self.vsf_elasticsearch_url)

    @classmethod
    def vsf_update(cls, shops=None):
        pool = Pool()
        Product = pool.get('product.product')
        ProductTemplate = pool.get('product.template')
        Category = pool.get('product.category')
        try:
            ProductAttribute = pool.get('product.attribute')
        except KeyError:
            ProductAttribute = None
        if shops is None:
            shops = cls.search([
                    ('type', '=', 'vsf'),
                    ])
        cls.lock(shops)
        for shop in shops:
            es = shop.get_vsf_elasticsearch()
            if ProductAttribute:
                attributes = shop.get_attributes()
                ProductAttribute.set_vsf_identifier(attributes)
            categories = shop.get_categories()
            Category.set_vsf_identifier(categories)
            products, prices, taxes = shop.get_products()
            Product.set_vsf_identifier(products)

            templates = set()
            for product in products:
                if product.vsf_is_configurable(shop):
                    templates.add(product.template)
                    continue
                entity = product.get_vsf_entity(
                    shop, price=prices[product.id], tax=taxes[product.id])
                es.index(
                    index=shop.vsf_elasticsearch_index,
                    doc_type='product',
                    id=product.vsf_identifier.id,
                    body=entity)
            templates = ProductTemplate.browse(templates)
            ProductTemplate.set_vsf_identifier(templates)
            for template in templates:
                template_products = template.get_vsf_products(shop)
                price, tax = min(
                    (prices[p.id], taxes[p.id]) for p in template_products)
                entity = template.get_vsf_entity(shop, price=price, tax=tax)
                entity['configurable_children'] = [
                    product.get_vsf_entity(
                        shop, price=prices[product.id], tax=taxes[product.id])
                    for product in template_products]
                es.index(
                    index=shop.vsf_elasticsearch_index,
                    doc_type='product',
                    id=template.vsf_identifier.id,
                    body=entity)

            for category in categories:
                entity = category.get_vsf_entity(shop)
                es.index(
                    index=shop.vsf_elasticsearch_index,
                    doc_type='category',
                    id=category.vsf_identifier.id,
                    body=entity)

            if ProductAttribute:
                for attribute in attributes:
                    entity = attribute.get_vsf_entity(shop)
                    es.index(
                        index=shop.vsf_elasticsearch_index,
                        doc_type='attribute',
                        id=attribute.vsf_identifier.id,
                        body=entity)

            for product in shop.products_removed:
                template = product.template
                if template.vsf_identifier:
                    template_products = product.template.get_vsf_products(shop)
                    if not template_products:
                        es.delete(
                            index=shop.vsf_elasticsearch_index,
                            doc_type='product',
                            id=template.vsf_identifier.id)
                if product.vsf_identifier:
                    es.delete(
                        index=shop.vsf_elasticsearch_index,
                        doc_type='product',
                        id=product.vsf_identifier.id)
            shop.products_removed = []

            for category in shop.categories_removed:
                if category.vsf_identifier:
                    es.delete(
                        index=shop.vsf_elasticsearch_index,
                        doc_type='category',
                        id=category.vsf_identifier.id)
            shop.categories_removed = []

            if ProductAttribute:
                for attribute in shop.attributes_removed:
                    if attribute.vsf_identifier:
                        es.delete(
                            index=shop.vsf_elasticsearch_index,
                            doc_type='attribute',
                            id=attribute.vsf_identifier.id)
                shop.attributes_removed = []

        cls.save(shops)

    def POST_vsf_user_create(self, data):
        pool = Pool()
        User = pool.get('web.user')
        Party = pool.get('party.party')
        firstname = data['customer']['firstname']
        lastname = data['customer']['lastname']
        email = data['customer']['email']
        user = User(email=email, password=data['password'])
        party = Party(name=join_name(firstname, lastname))
        user.party = party
        user.save()
        firstname, lastname = split_name(user.party.name)
        return {
            'email': user.email,
            'firstname': firstname,
            'lastname': lastname,
            'addresses': [],
            }

    def POST_vsf_user_login(self, data):
        pool = Pool()
        User = pool.get('web.user')
        try:
            user = User.authenticate(data['username'], data['password'])
        except RateLimitException:
            raise LoginException(gettext(
                    'web_shop_vue_storefront.msg_login_wrong'))
        if user:
            return user.new_session()
        else:
            raise LoginException(gettext(
                    'web_shop_vue_storefront.msg_login_wrong'))

    def POST_vsf_user_reset_password(self, data):
        pool = Pool()
        User = pool.get('web.user')
        users = User.search([
                ('email', '=', data['email']),
                ])
        User.reset_password(users)

    @with_user(required=True)
    def POST_vsf_user_change_password(self, data, user):
        pool = Pool()
        User = pool.get('web.user')
        try:
            user = User.authenticate(user.email, data['currentPassword'])
        except RateLimitException:
            raise LoginException(gettext(
                    'web_shop_vue_storefront.msg_login_wrong'))
        if user:
            user.password = data['newPassword']
            user.save()
        else:
            raise LoginException(gettext(
                    'web_shop_vue_storefront.msg_login_wrong'))

    @with_user(required=True)
    def GET_vsf_user_order_history(
            self, data, user, pageSize='20', currentPage='1'):
        pool = Pool()
        Sale = pool.get('sale.sale')
        try:
            pageSize = int(pageSize)
            currentPage = int(currentPage)
        except ValueError:
            raise BadRequest()
        sales = Sale.search([
                ('party', '=', user.party),
                ('state', 'in', ['confirmed', 'processing', 'done']),
                ],
            offset=pageSize * (currentPage - 1),
            limit=pageSize,
            order=[
                ('sale_date', 'DESC'),
                ('id', 'DESC'),
                ])
        items = []
        for sale in sales:
            items.append(sale.get_vsf_user_order_history())
        return {'items': items}

    @with_user(required=True)
    def GET_vsf_user_me(self, data, user):
        return user.get_vsf()

    @with_user(required=True)
    def POST_vsf_user_me(self, data, user):
        user.set_vsf(data['customer'])
        user.save()
        return user.get_vsf()

    def GET_vsf_stock_check(self, data, sku):
        try:
            return self.GET_vsf_stock_list(data, sku)[0]
        except IndexError:
            raise NotFound()

    def GET_vsf_stock_list(self, data, skus):
        pool = Pool()
        Product = pool.get('product.product')
        Template = pool.get('product.template')
        skus = skus.split(',')
        products = Product.search([
                ('vsf_sku', 'in', skus),
                ('web_shops', '=', self.id),
                ])
        products += Template.search([
                ('vsf_sku', 'in', skus),
                ('products.web_shops', '=', self.id),
                ])
        return [p.get_vsf_stock() for p in products]

    @with_user()
    def POST_vsf_cart_create(self, data, user=None):
        party = user.party if user else None
        sale = self.get_sale(party)
        sale.save()
        return sale.vsf_id

    @with_user()
    def GET_vsf_cart_pull(self, data, cartId, user=None):
        pool = Pool()
        Sale = pool.get('sale.sale')
        sale = Sale.search_vsf(cartId, self, user)
        return [line.get_vsf() for line in sale.lines if line.product]

    @with_user()
    def POST_vsf_cart_update(self, data, cartId, user=None):
        pool = Pool()
        Sale = pool.get('sale.sale')
        SaleLine = pool.get('sale.line')
        sale = Sale.search_vsf(cartId, self, user)
        if data['cartItem'].get('item_id'):
            line = SaleLine(data['cartItem']['item_id'])
            if line.sale != sale:
                raise BadRequest()
        else:
            line = SaleLine(sale=sale)
        line.set_vsf(data['cartItem'])
        line.save()
        return line.get_vsf()

    @with_user()
    def POST_vsf_cart_delete(self, data, cartId, user=None):
        pool = Pool()
        Sale = pool.get('sale.sale')
        SaleLine = pool.get('sale.line')
        sale = Sale.search_vsf(cartId, self, user)
        line = SaleLine(data['cartItem']['item_id'])
        if line.sale != sale:
            raise BadRequest()
        SaleLine.delete([line])
        return True

    @with_user()
    def GET_vsf_cart_totals(self, data, cartId, user=None):
        pool = Pool()
        Sale = pool.get('sale.sale')
        sale = Sale.search_vsf(cartId, self, user)
        return sale.get_vsf()

    @with_user()
    def GET_vsf_cart_payment_methods(self, data, cartId, user=None):
        return []

    @with_user()
    def POST_vsf_cart_shipping_methods(self, data, cartId, user=None):
        return []

    @with_user()
    def POST_vsf_cart_shipping_information(self, data, cartId, user=None):
        pool = Pool()
        Sale = pool.get('sale.sale')
        sale = Sale.search_vsf(cartId, self, user)
        return sale.get_vsf()

    @with_user(required=True)
    def POST_vsf_order_create(self, data, cartId, user):
        pool = Pool()
        Sale = pool.get('sale.sale')
        sale = Sale.search_vsf(cartId, self, user)
        self.vsf_order_create(data, sale, user)
        return 'OK'

    def vsf_order_create(self, data, sale, user):
        pool = Pool()
        Sale = pool.get('sale.sale')
        SaleLine = pool.get('sale.line')
        sale.set_vsf(data, user)
        sku2lines = {
            line.product.vsf_sku: line for line in sale.lines if line.product}
        for product in data.get('products', []):
            sku = product['sku']
            line = sku2lines.get(sku)
            if not line:
                line = SaleLine(sale=sale)
                sku2lines[sku] = line
            line.set_vsf(product)
        sale.lines = sku2lines.values()
        sale.save()
        Sale.quote([sale])
        payment_method = data['addressInformation']['payment_method_code']
        if payment_method == 'cashondelivery':
            Sale.confirm([sale])
        return sale


class ShopCoupon(metaclass=PoolMeta):
    __name__ = 'web.shop'

    @with_user()
    def POST_vsf_cart_apply_coupon(self, data, cartId, coupon, user=None):
        pool = Pool()
        Sale = pool.get('sale.sale')
        sale = Sale.search_vsf(cartId, self, user)
        PromotionCouponNumber = pool.get('sale.promotion.coupon.number')
        try:
            coupon, = PromotionCouponNumber.search([
                    ('number', 'ilike', coupon),
                    ], limit=1)
        except ValueError:
            return False
        sale.coupons = [coupon]
        sale.save()
        return True

    @with_user()
    def POST_vsf_cart_delete_coupon(self, data, cartId, user=None):
        pool = Pool()
        Sale = pool.get('sale.sale')
        sale = Sale.search_vsf(cartId, self, user)
        sale.coupons = []
        sale.save()
        return True

    @with_user()
    def POST_vsf_cart_coupon(self, data, cartId, user=None):
        pool = Pool()
        Sale = pool.get('sale.sale')
        sale = Sale.search_vsf(cartId, self, user)
        if sale.coupons:
            return sale.coupons[0].number
        else:
            return ''


class ShopShipmentCost(metaclass=PoolMeta):
    __name__ = 'web.shop'

    @with_user()
    def POST_vsf_cart_shipping_methods(self, data, cartId, user=None):
        pool = Pool()
        Sale = pool.get('sale.sale')
        methods = super().POST_vsf_cart_shipping_methods(
            data, cartId, user=user)
        sale = Sale.search_vsf(cartId, self, user)
        sale.set_vsf_shipping_methods(data)
        for carrier in sale.available_carriers:
            method = carrier.get_vsf()
            sale.carrier = carrier
            method['price_incl_tax'] = sale.compute_shipment_cost()
            methods.append(method)
        return methods

    @with_user()
    def POST_vsf_cart_shipping_information(self, data, cartId, user=None):
        pool = Pool()
        Sale = pool.get('sale.sale')
        sale = Sale.search_vsf(cartId, self, user)
        sale.set_vsf(data, user)
        sale.save()
        return super().POST_vsf_cart_shipping_information(
            data, cartId, user=user)


class ShopVSFIdentifier(ModelSQL):
    "Web Shop Vue Storefront Identifier"
    __name__ = 'web.shop.vsf_identifier'

    record = fields.Reference("Record", 'get_records', required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('record_unique', Unique(t, t.record),
                'web_shop_vue_storefront.msg_identifier_record_unique'),
            ]

    @classmethod
    def get_records(cls):
        pool = Pool()
        Model = pool.get('ir.model')
        models = [klass.__name__ for _, klass in pool.iterobject()
            if issubclass(klass, ShopVSFIdentifierMixin)]
        models = Model.search([
                ('model', 'in', models),
                ])
        return [(m.model, m.name) for m in models]


class ShopVSFIdentifierMixin:

    vsf_identifier = fields.Many2One(
        'web.shop.vsf_identifier',
        lazy_gettext('web_shop_vue_storefront.msg_vsf_identifier'),
        ondelete='RESTRICT', readonly=True)

    @classmethod
    def set_vsf_identifier(cls, records):
        pool = Pool()
        Identifier = pool.get('web.shop.vsf_identifier')
        for record in records:
            if not record.vsf_identifier:
                record.vsf_identifier = Identifier(record=record)
        cls.save(records)


class User(metaclass=PoolMeta):
    __name__ = 'web.user'

    def get_vsf(self):
        if not self.party:
            return {
                'email': self.email,
                }
        firstname, lastname = split_name(self.party.name)
        data = {
            'email': self.email,
            'firstname': firstname,
            'lastname': lastname,
            'addresses': (
                [a.get_vsf() for a in self.party.addresses]
                + [a.get_vsf(self.party) for p in self.secondary_parties
                    for a in p.addresses if p != self.party]),
            }

        default_billing = self.invoice_address
        if not default_billing:
            default_billing = self.party.address_get('invoice')
        if default_billing:
            data['default_billing'] = default_billing.id

        default_shipping = self.shipment_address
        if not default_shipping:
            default_shipping = self.party.address_get('delivery')
        if default_shipping:
            data['default_shipping'] = default_shipping.id

        return data

    def set_vsf(self, data):
        pool = Pool()
        Party = pool.get('party.party')
        Address = pool.get('party.address')
        self.email = data['email']
        if not self.party:
            self.party = Party()
        self.party.name = join_name(data['firstname'], data['lastname'])

        default_billing = None
        default_shipping = None
        addresses = []
        for address_data in data['addresses']:
            address = self.set_vsf_address(address_data, self.party)
            addresses.append(address)
            if ((address.id and address.id == data.get('default_billing'))
                    or address_data.get('default_billing')):
                default_billing = address
            if ((address.id and address.id == data.get('default_shipping'))
                    or address_data.get('default_shipping')):
                default_shipping = address

            if address_data.get('id'):
                if address_data['id'] != address.id:
                    address = Address(address_data['id'])
                    if (address.party != self.party
                            and address.party not in self.secondary_parties):
                        raise BadRequest()
                    address.active = False
                    addresses.append(address)
        Address.save(addresses)
        self.invoice_address = default_billing
        self.shipment_address = default_shipping

    def set_vsf_address(self, address_data, party):
        pool = Pool()
        Party = pool.get('party.party')
        Address = pool.get('party.address')
        Identifier = pool.get('party.identifier')

        addresses = self.party.addresses
        for party in self.secondary_parties:
            addresses += party.addresses

        for address in addresses:
            if issubdict(address.get_vsf(party), address_data):
                return address

        address = Address()
        party = address.party = self.party
        if address_data.get('company'):
            for company_party in self.secondary_parties:
                tax_code = (
                    company_party.tax_identifier.code
                    if company_party.tax_identifier else '')
                if (company_party.name == address_data['company']
                        and (not address_data.get('vat_id')
                            or tax_code == address_data['vat_id'])):
                    break
            else:
                identifier = Identifier()
                identifier.set_vsf_tax_identifier(
                    address_data['vat_id'])
                company_party = Party(
                    name=address_data['company'],
                    identifiers=[identifier])
                company_party.save()
                self.secondary_parties += (company_party,)
                self.save()
            address.party = company_party
        address.set_vsf(address_data, party)
        return address
