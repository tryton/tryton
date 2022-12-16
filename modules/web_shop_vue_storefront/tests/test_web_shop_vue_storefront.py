# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest
import doctest
from contextlib import contextmanager
from decimal import Decimal

from unittest.mock import patch, ANY

from werkzeug.exceptions import Unauthorized

from trytond.pool import Pool
from trytond.tests.test_tryton import doctest_teardown, doctest_checker
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.tests.test_tryton import suite as test_suite
from trytond.transaction import Transaction
from trytond.modules.company.tests import create_company, set_company
from ..exceptions import LoginException

CUSTOMER = {
    'email': 'customer@example.com',
    'firstname': 'John',
    'lastname': 'Doe',
    }
ADDRESS = {
    'region': {
        'region': None,
        },
    'country_id': "US",
    'street': [
        "Cliff Street",
        "300"
        ],
    'telephone': '+1 202-555-0148',
    'postcode': '18503',
    'city': "Scranton",
    'firstname': CUSTOMER['firstname'],
    'lastname': CUSTOMER['lastname'],
    }
ADDRESS_COMPANY = ADDRESS.copy()
ADDRESS_COMPANY['company'] = 'Saber'
ADDRESS_COMPANY['vat_id'] = 'BE0500923836'


class WebVueStorefrontTestCase(ModuleTestCase):
    'Test Web Shop Vue Storefront module'
    module = 'web_shop_vue_storefront'
    extras = [
        'product_attribute',
        'sale_promotion_coupon',
        'sale_shipment_cost',
        'carrier',
        ]
    maxDiff = None

    @contextmanager
    def create_web_shop(self):
        pool = Pool()
        WebShop = pool.get('web.shop')
        Location = pool.get('stock.location')
        Party = pool.get('party.party')

        company = create_company()
        warehouse, = Location.search([('type', '=', 'warehouse')], limit=1)
        web_shop = WebShop(name="Web Shop")
        web_shop.company = company
        web_shop.currency = company.currency
        web_shop.warehouses = [warehouse]
        web_shop.type = 'vsf'
        web_shop.guest_party = Party(name="Guest")
        web_shop.save()
        with Transaction().set_context(**web_shop.get_context()):
            yield web_shop

    def create_product(self, web_shop, quantity=0, code="CODE"):
        pool = Pool()
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Category = pool.get('product.category')
        Uom = pool.get('product.uom')
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')

        unit, = Uom.search([('name', '=', "Unit")], limit=1)
        template = Template(name="Product")
        template.type = 'goods'
        template.list_price = Decimal(100)
        template.default_uom = unit
        template.salable = True
        template.sale_uom = unit
        template.products = [Product(suffix_code=code, web_shops=[web_shop])]
        template.account_category = Category(name="Category", accounting=True)
        template.save()
        product, = template.products

        if quantity:
            supplier, = Location.search([('code', '=', 'SUP')])
            storage, = Location.search([('code', '=', 'STO')])
            with set_company(web_shop.company):
                move = Move(product=product)
                move.uom = unit
                move.quantity = quantity
                move.from_location = supplier
                move.to_location = storage
                move.unit_price = Decimal(50)
                move.save()
                Move.do([move])
        Product.set_vsf_identifier([product])
        return product

    def create_coupon(self, code='CODE'):
        pool = Pool()
        Promotion = pool.get('sale.promotion')
        Coupon = pool.get('sale.promotion.coupon')

        promotion = Promotion(name="10%")
        promotion.formula = '0.9 * unit_price'
        promotion.coupons = coupon, = [Coupon(name="Promo")]
        coupon.numbers = [{'number': code}]
        promotion.save()

    def create_carrier(
            self, name='Carrier', product_name="Delivery",
            price=Decimal('10')):
        pool = Pool()
        Carrier = pool.get('carrier')
        Party = pool.get('party.party')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Category = pool.get('product.category')
        Uom = pool.get('product.uom')

        unit, = Uom.search([('name', '=', "Unit")], limit=1)
        template = Template(name=product_name)
        template.type = 'service'
        template.list_price = price
        template.default_uom = template.sale_uom = unit
        template.salable = True
        template.products = [Product()]
        template.account_category = Category(name="Service", accounting=True)
        template.save()

        carrier = Carrier()
        carrier.party = Party(name=name)
        carrier.carrier_product, = template.products
        carrier.save()
        return carrier

    @with_transaction(user=0)
    def test_user_create(self):
        pool = Pool()
        User = pool.get('web.user')
        with self.create_web_shop() as web_shop:
            result = web_shop.POST_vsf_user_create({
                    "customer": CUSTOMER,
                    "password": "SecretPassword"
                    })
            users = User.search([])

            self.assertEqual(result, {
                    "email": CUSTOMER['email'],
                    "firstname": CUSTOMER['firstname'],
                    "lastname": CUSTOMER['lastname'],
                    "addresses": [],
                    })
            self.assertEqual(len(users), 1)

    @with_transaction(user=0)
    def test_user_login(self):
        with self.create_web_shop() as web_shop:
            web_shop.POST_vsf_user_create({
                    "customer": CUSTOMER,
                    "password": "TopSecretPassword",
                    })

            result = web_shop.POST_vsf_user_login({
                    "username": CUSTOMER['email'],
                    "password": "TopSecretPassword",
                    })

            self.assertTrue(result)

    @with_transaction(user=0)
    def test_user_login_wrong_password(self):
        with self.create_web_shop() as web_shop:
            web_shop.POST_vsf_user_create({
                    "customer": CUSTOMER,
                    "password": "TopSecretPassword",
                    })

            with self.assertRaises(LoginException):
                web_shop.POST_vsf_user_login({
                        "username": CUSTOMER['email'],
                        "password": "Bad",
                        })

    @with_transaction(user=0)
    def test_user_reset_password(self):
        pool = Pool()
        User = pool.get('web.user')
        with self.create_web_shop() as web_shop:
            web_shop.POST_vsf_user_create({
                    "customer": CUSTOMER,
                    "password": "SecretPassword",
                    })

            with patch.object(User, 'reset_password') as reset_password:
                result = web_shop.POST_vsf_user_reset_password({
                        "email": CUSTOMER['email'],
                        })

            self.assertFalse(result)
            reset_password.assert_called_once_with(ANY)

    @with_transaction(user=0)
    def test_user_change_password(self):
        with self.create_web_shop() as web_shop:
            web_shop.POST_vsf_user_create({
                    "customer": CUSTOMER,
                    "password": "OldPassword",
                    })
            token = web_shop.POST_vsf_user_login({
                    "username": CUSTOMER['email'],
                    "password": "OldPassword",
                    })

            result = web_shop.POST_vsf_user_change_password({
                    "currentPassword": "OldPassword",
                    "newPassword": "NewPassword",
                    }, token=token)

            self.assertFalse(result)

    @with_transaction(user=0)
    def test_user_change_password_wrong_token(self):
        with self.create_web_shop() as web_shop:
            web_shop.POST_vsf_user_create({
                    "customer": CUSTOMER,
                    "password": "OldPassword",
                    })

            with self.assertRaises(Unauthorized):
                web_shop.POST_vsf_user_change_password({
                        "currentPassword": "BadPassword",
                        "newPassword": "NewPassword",
                        }, 'wrong token')

    @with_transaction(user=0)
    def test_user_change_password_wrong_password(self):
        with self.create_web_shop() as web_shop:
            web_shop.POST_vsf_user_create({
                    "customer": CUSTOMER,
                    "password": "OldPassword",
                    })
            token = web_shop.POST_vsf_user_login({
                    "username": CUSTOMER['email'],
                    "password": "OldPassword",
                    })

            with self.assertRaises(LoginException):
                web_shop.POST_vsf_user_change_password({
                        "currentPassword": "BadPassword",
                        "newPassword": "NewPassword",
                        }, token=token)

    @with_transaction(user=0)
    def test_user_order_history(self):
        pool = Pool()
        Country = pool.get('country.country')
        Country(name="US", code="US").save()
        with self.create_web_shop() as web_shop:
            self.create_product(web_shop)
            web_shop.POST_vsf_user_create({
                    "customer": CUSTOMER,
                    "password": "TopSecretPassword",
                    })
            token = web_shop.POST_vsf_user_login({
                    "username": CUSTOMER['email'],
                    "password": "TopSecretPassword",
                    })
            cart = web_shop.POST_vsf_cart_create(None, token=token)
            web_shop.POST_vsf_order_create({
                    'products': [{
                            'sku': 'CODE',
                            'qty': 2,
                            }],
                    'addressInformation': {
                        'shippingAddress': ADDRESS,
                        'billingAddress': ADDRESS_COMPANY,
                        'shipping_method_code': None,
                        'shipping_carrier_code': None,
                        'payment_method_code': 'cashondelivery',
                        'payment_method_additional': {},
                        },
                    }, cart, token=token)

            items = web_shop.GET_vsf_user_order_history(None, token=token)

            self.assertEqual(items, {
                    'items': [{
                            'entity_id': ANY,
                            'increment_id': ANY,
                            'created_at': ANY,
                            'customer_firstname': CUSTOMER['firstname'],
                            'customer_lastname': CUSTOMER['lastname'],
                            'grand_total': 200,
                            'status': "Confirmed",
                            'items': [{
                                    'name': "Product",
                                    'sku': 'CODE',
                                    'price_incl_tax': 100,
                                    'qty_ordered': 2,
                                    'row_total_incl_tax': 200,
                                    }],
                            }],
                    })

    @with_transaction(user=0)
    def test_user_order_history_wrong_token(self):
        with self.create_web_shop() as web_shop:
            with self.assertRaises(Unauthorized):
                web_shop.GET_vsf_user_order_history(None, 'wrong token')

    @with_transaction(user=0)
    def test_user_me(self):
        pool = Pool()
        Country = pool.get('country.country')
        Country(name="US", code="US").save()
        with self.create_web_shop() as web_shop:
            web_shop.POST_vsf_user_create({
                    "customer": CUSTOMER,
                    "password": "TopSecretPassword",
                    })
            token = web_shop.POST_vsf_user_login({
                    "username": CUSTOMER['email'],
                    "password": "TopSecretPassword",
                    })

            result = web_shop.GET_vsf_user_me(None, token=token)

            data = {'customer': CUSTOMER.copy()}
            data['customer']['addresses'] = []
            self.assertEqual(result, data['customer'])

            data = {'customer': CUSTOMER.copy()}
            data['customer']['addresses'] = [ADDRESS_COMPANY.copy()]
            result = web_shop.POST_vsf_user_me(data, token=token)

            data['customer']['addresses'][0]['id'] = ANY
            data['customer']['addresses'][0].pop('region')
            self.assertEqual(result, data['customer'])

    @with_transaction(user=0)
    def test_user_me_wrong_token(self):
        with self.create_web_shop() as web_shop:

            with self.assertRaises(Unauthorized):
                web_shop.GET_vsf_user_me(None, 'wrong token')

            with self.assertRaises(Unauthorized):
                web_shop.POST_vsf_user_me({}, 'wrong token')

    @with_transaction(user=0)
    def test_user_me_change_address(self):
        pool = Pool()
        Address = pool.get('party.address')
        Country = pool.get('country.country')
        Country(name="US", code="US").save()
        with self.create_web_shop() as web_shop:
            web_shop.POST_vsf_user_create({
                    "customer": CUSTOMER,
                    "password": "TopSecretPassword",
                    })
            token = web_shop.POST_vsf_user_login({
                    "username": CUSTOMER['email'],
                    "password": "TopSecretPassword",
                    })
            data = {'customer': CUSTOMER.copy()}
            data['customer']['addresses'] = [ADDRESS_COMPANY]
            result = web_shop.POST_vsf_user_me(data, token=token)

            data = {'customer': CUSTOMER.copy()}
            address = ADDRESS.copy()
            address['lastname'] = "Scott"
            data['customer']['addresses'] = [address]
            result = web_shop.POST_vsf_user_me(
                {"customer": result}, token=token)

            inactive_addresses = Address.search([('active', '=', False)])
            self.assertEqual(len(inactive_addresses), 1)

    @with_transaction(user=0)
    def test_stock_check(self):
        with self.create_web_shop() as web_shop:
            product = self.create_product(web_shop, quantity=10)

            result = web_shop.GET_vsf_stock_check(None, product.vsf_sku)

            self.assertEqual(result, {
                    'product_id': product.vsf_identifier.id,
                    'qty': 10,
                    'is_in_stock': True,
                    })

    @with_transaction(user=0)
    def test_stock_list(self):
        with self.create_web_shop() as web_shop:
            product1 = self.create_product(web_shop, quantity=10)
            product2 = self.create_product(web_shop, quantity=0, code="CODE2")

            result = web_shop.GET_vsf_stock_list(
                None, ','.join([p.vsf_sku for p in [product1, product2]]))

            self.assertEqual(result, [{
                        'product_id': product1.vsf_identifier.id,
                        'qty': 10,
                        'is_in_stock': True,
                        }, {
                        'product_id': product2.vsf_identifier.id,
                        'qty': 0,
                        'is_in_stock': False,
                        }])

    @with_transaction(user=0)
    def test_cart_create_without_token(self):
        with self.create_web_shop() as web_shop:
            cart = web_shop.POST_vsf_cart_create(None)

            self.assertIsInstance(cart, str)

    @with_transaction(user=0)
    def test_cart_create_with_token(self):
        with self.create_web_shop() as web_shop:
            web_shop.POST_vsf_user_create({
                    "customer": CUSTOMER,
                    "password": "TopSecretPassword",
                    })
            token = web_shop.POST_vsf_user_login({
                    "username": CUSTOMER['email'],
                    "password": "TopSecretPassword",
                    })

            cart = web_shop.POST_vsf_cart_create(None, token=token)

            self.assertIsInstance(cart, int)

    @with_transaction(user=0)
    def test_cart_pull_without_token(self):
        with self.create_web_shop() as web_shop:
            self.create_product(web_shop)
            cart = web_shop.POST_vsf_cart_create(None)
            web_shop.POST_vsf_cart_update({
                    'cartItem': {
                        'sku': 'CODE',
                        'qty': 1,
                        },
                    }, cart)

            items = web_shop.GET_vsf_cart_pull(None, cart)

            self.assertEqual(items, [{
                        'item_id': ANY,
                        'sku': 'CODE',
                        'qty': 1,
                        'name': 'Product',
                        'price': 100,
                        'product_type': 'simple',
                        'quote_id': ANY,
                        'product_option': {
                            'extension_attributes': {},
                            },
                        }])

    @with_transaction(user=0)
    def test_cart_pull_with_token(self):
        with self.create_web_shop() as web_shop:
            self.create_product(web_shop)
            web_shop.POST_vsf_user_create({
                    "customer": CUSTOMER,
                    "password": "TopSecretPassword",
                    })
            token = web_shop.POST_vsf_user_login({
                    "username": CUSTOMER['email'],
                    "password": "TopSecretPassword",
                    })
            cart = web_shop.POST_vsf_cart_create(None, token=token)
            web_shop.POST_vsf_cart_update({
                    'cartItem': {
                        'sku': 'CODE',
                        'qty': 1,
                        },
                    }, cart, token=token)

            items = web_shop.GET_vsf_cart_pull(None, cart, token=token)

            self.assertEqual(items, [{
                        'item_id': ANY,
                        'sku': 'CODE',
                        'qty': 1,
                        'name': 'Product',
                        'price': 100,
                        'product_type': 'simple',
                        'quote_id': ANY,
                        'product_option': {
                            'extension_attributes': {},
                            },
                        }])

    @with_transaction(user=0)
    def test_cart_update_without_token(self):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        with self.create_web_shop() as web_shop:
            self.create_product(web_shop)
            cart = web_shop.POST_vsf_cart_create(None)

            item = web_shop.POST_vsf_cart_update({
                    'cartItem': {
                        'sku': 'CODE',
                        'qty': 1,
                        },
                    }, cart)

            self.assertEqual(item, {
                    'item_id': ANY,
                    'sku': 'CODE',
                    'qty': 1,
                    'name': 'Product',
                    'price': 100,
                    'product_type': 'simple',
                    'quote_id': ANY,
                    'product_option': {
                        'extension_attributes': {},
                        },
                    })
            sale_lines = SaleLine.search([])
            self.assertEqual(len(sale_lines), 1)

    @with_transaction(user=0)
    def test_cart_update_with_token(self):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        with self.create_web_shop() as web_shop:
            self.create_product(web_shop)
            web_shop.POST_vsf_user_create({
                    "customer": CUSTOMER,
                    "password": "TopSecretPassword",
                    })
            token = web_shop.POST_vsf_user_login({
                    "username": CUSTOMER['email'],
                    "password": "TopSecretPassword",
                    })
            cart = web_shop.POST_vsf_cart_create(None, token=token)

            item = web_shop.POST_vsf_cart_update({
                    'cartItem': {
                        'sku': 'CODE',
                        'qty': 1,
                        },
                    }, cart, token=token)

            self.assertEqual(item, {
                    'item_id': ANY,
                    'sku': 'CODE',
                    'qty': 1,
                    'name': 'Product',
                    'price': 100,
                    'product_type': 'simple',
                    'quote_id': ANY,
                    'product_option': {
                        'extension_attributes': {},
                        },
                    })
            sale_lines = SaleLine.search([])
            self.assertEqual(len(sale_lines), 1)

    @with_transaction(user=0)
    def test_cart_update2(self):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        with self.create_web_shop() as web_shop:
            self.create_product(web_shop)
            cart = web_shop.POST_vsf_cart_create(None)
            item = web_shop.POST_vsf_cart_update({
                    'cartItem': {
                        'sku': 'CODE',
                        'qty': 1,
                        },
                    }, cart)

            item = web_shop.POST_vsf_cart_update({
                    'cartItem': {
                        'sku': 'CODE',
                        'qty': 2,
                        'item_id': item['item_id'],
                        },
                    }, cart)

            self.assertEqual(item, {
                    'item_id': ANY,
                    'sku': 'CODE',
                    'qty': 2,
                    'name': 'Product',
                    'price': 100,
                    'product_type': 'simple',
                    'quote_id': ANY,
                    'product_option': {
                        'extension_attributes': {},
                        },
                    })
            sale_lines = SaleLine.search([])
            self.assertEqual(len(sale_lines), 1)

    @with_transaction(user=0)
    def test_cart_delete(self):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        with self.create_web_shop() as web_shop:
            self.create_product(web_shop)
            cart = web_shop.POST_vsf_cart_create(None)
            item = web_shop.POST_vsf_cart_update({
                    'cartItem': {
                        'sku': 'CODE',
                        'qty': 1,
                        },
                    }, cart)

            result = web_shop.POST_vsf_cart_delete({
                    'cartItem': {
                        'sku': 'CODE',
                        'qty': 1,
                        'item_id': item['item_id'],
                        },
                    }, cart)

            self.assertTrue(result)
            sale_lines = SaleLine.search([])
            self.assertEqual(len(sale_lines), 0)

    @with_transaction(user=0)
    def test_cart_apply_coupon(self):
        with self.create_web_shop() as web_shop:
            self.create_coupon()
            cart = web_shop.POST_vsf_cart_create(None)

            result = web_shop.POST_vsf_cart_apply_coupon(None, cart, 'CODE')

            self.assertTrue(result)

    @with_transaction(user=0)
    def test_cart_delete_coupon(self):
        with self.create_web_shop() as web_shop:
            self.create_coupon()
            cart = web_shop.POST_vsf_cart_create(None)
            web_shop.POST_vsf_cart_apply_coupon(None, cart, 'CODE')

            result = web_shop.POST_vsf_cart_delete_coupon(None, cart)

            self.assertTrue(result)

    @with_transaction(user=0)
    def test_cart_coupon(self):
        with self.create_web_shop() as web_shop:
            self.create_coupon()
            cart = web_shop.POST_vsf_cart_create(None)
            web_shop.POST_vsf_cart_apply_coupon(None, cart, 'CODE')

            result = web_shop.POST_vsf_cart_coupon(None, cart)

            self.assertEqual(result, 'CODE')

    @with_transaction(user=0)
    def test_cart_coupon_empty(self):
        with self.create_web_shop() as web_shop:
            cart = web_shop.POST_vsf_cart_create(None)

            result = web_shop.POST_vsf_cart_coupon(None, cart)

            self.assertEqual(result, '')

    @with_transaction(user=0)
    def test_cart_totals(self):
        with self.create_web_shop() as web_shop:
            self.create_product(web_shop)
            cart = web_shop.POST_vsf_cart_create(None)
            web_shop.POST_vsf_cart_update({
                    'cartItem': {
                        'sku': 'CODE',
                        'qty': 1,
                        },
                    }, cart)

            totals = web_shop.GET_vsf_cart_totals(None, cart)

            self.assertEqual(totals, {
                    'grand_total': 100,
                    'items': [{
                            'item_id': ANY,
                            'sku': 'CODE',
                            'qty': 1,
                            'name': 'Product',
                            'price': 100,
                            'product_type': 'simple',
                            'quote_id': ANY,
                            'product_option': {
                                'extension_attributes': {
                                    },
                                },
                            }],
                    'total_segments': [{
                            'code': 'subtotal',
                            'title': ANY,
                            'value': 100,
                            }, {
                            'code': 'tax',
                            'title': ANY,
                            'value': 0,
                            }, {
                            'code': 'grand_total',
                            'title': ANY,
                            'value': 100,
                            }],
                    })

    @with_transaction(user=0)
    def test_cart_payment_methods(self):
        with self.create_web_shop() as web_shop:
            cart = web_shop.POST_vsf_cart_create(None)

            result = web_shop.GET_vsf_cart_payment_methods(None, cart)

            self.assertEqual(result, [])

    @with_transaction(user=0)
    def test_cart_shipping_methods(self):
        pool = Pool()
        Country = pool.get('country.country')
        Country(name="US", code="US").save()
        with self.create_web_shop() as web_shop:
            carrier = self.create_carrier()
            self.create_product(web_shop)
            cart = web_shop.POST_vsf_cart_create(None)
            web_shop.POST_vsf_cart_update({
                    'cartItem': {
                        'sku': 'CODE',
                        'qty': 1,
                        },
                    }, cart)

            methods = web_shop.POST_vsf_cart_shipping_methods(
                {'address': {'country_id': 'US'}}, cart)

            self.assertEqual(methods, [{
                        'carrier_code': str(carrier.id),
                        'method_code': str(carrier.id),
                        'carrier_title': "Carrier",
                        'method_title': "Delivery",
                        'price_incl_tax': Decimal(10),
                        }])

    @with_transaction(user=0)
    def test_cart_shipping_information(self):
        pool = Pool()
        Country = pool.get('country.country')
        Country(name="US", code="US").save()
        with self.create_web_shop() as web_shop:
            carrier = self.create_carrier()
            self.create_product(web_shop)
            cart = web_shop.POST_vsf_cart_create(None)
            web_shop.POST_vsf_cart_update({
                    'cartItem': {
                        'sku': 'CODE',
                        'qty': 1,
                        },
                    }, cart)

            information = web_shop.POST_vsf_cart_shipping_information({
                    'addressInformation': {
                        'shipping_address': {
                            'country_id': 'US',
                            },
                        'shipping_method_code': str(carrier.id),
                        'shipping_carrier_code': str(carrier.id),
                        },
                    }, cart)

            self.assertEqual(information, {
                    'grand_total': 110,
                    'items': ANY,
                    'total_segments': [{
                            'code': 'subtotal',
                            'title': ANY,
                            'value': 100,
                            }, {
                            'code': 'shipping',
                            'title': ANY,
                            'value': 10,
                            }, {
                            'code': 'tax',
                            'title': ANY,
                            'value': 0,
                            }, {
                            'code': 'grand_total',
                            'title': ANY,
                            'value': 110,
                            }],
                    })

    @with_transaction(user=0)
    def test_order_create(self):
        pool = Pool()
        Sale = pool.get('sale.sale')
        Country = pool.get('country.country')
        Country(name="US", code="US").save()
        with self.create_web_shop() as web_shop:
            carrier = self.create_carrier()
            self.create_product(web_shop)
            web_shop.POST_vsf_user_create({
                    "customer": CUSTOMER,
                    "password": "TopSecretPassword",
                    })
            token = web_shop.POST_vsf_user_login({
                    "username": CUSTOMER['email'],
                    "password": "TopSecretPassword",
                    })
            cart = web_shop.POST_vsf_cart_create(None, token=token)
            web_shop.POST_vsf_cart_update({
                    'cartItem': {
                        'sku': 'CODE',
                        'qty': 1,
                        },
                    }, cart, token=token)

            result = web_shop.POST_vsf_order_create({
                    'products': [{
                            'sku': 'CODE',
                            'qty': 1,
                            }],
                    'addressInformation': {
                        'shippingAddress': ADDRESS,
                        'billingAddress': ADDRESS_COMPANY,
                        'shipping_method_code': str(carrier.id),
                        'shipping_carrier_code': str(carrier.id),
                        'payment_method_code': 'cashondelivery',
                        'payment_method_additional': {},
                        },
                    }, cart, token=token)

            self.assertEqual(result, 'OK')

            sale, = Sale.search([])
            self.assertEqual(sale.state, 'confirmed')
            self.assertEqual(len(sale.lines), 2)
            self.assertEqual(sale.total_amount, Decimal(110))

    @with_transaction(user=0)
    def test_order_create_from_guest(self):
        pool = Pool()
        Sale = pool.get('sale.sale')
        Country = pool.get('country.country')
        Country(name="US", code="US").save()
        with self.create_web_shop() as web_shop:
            carrier = self.create_carrier()
            self.create_product(web_shop)
            cart = web_shop.POST_vsf_cart_create(None)
            web_shop.POST_vsf_cart_update({
                    'cartItem': {
                        'sku': 'CODE',
                        'qty': 1,
                        },
                    }, cart)
            web_shop.POST_vsf_user_create({
                    "customer": CUSTOMER,
                    "password": "TopSecretPassword",
                    })
            token = web_shop.POST_vsf_user_login({
                    "username": CUSTOMER['email'],
                    "password": "TopSecretPassword",
                    })
            result = web_shop.POST_vsf_order_create({
                    'products': [{
                            'sku': 'CODE',
                            'qty': 1,
                            }],
                    'addressInformation': {
                        'shippingAddress': ADDRESS,
                        'billingAddress': ADDRESS_COMPANY,
                        'shipping_method_code': str(carrier.id),
                        'shipping_carrier_code': str(carrier.id),
                        'payment_method_code': 'cashondelivery',
                        'payment_method_additional': {},
                        },
                    }, cart, token=token)

            self.assertEqual(result, 'OK')

            sale, = Sale.search([])
            self.assertNotEqual(sale.party, web_shop.guest_party)
            self.assertEqual(sale.state, 'confirmed')
            self.assertEqual(len(sale.lines), 2)
            self.assertEqual(sale.total_amount, Decimal(110))


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            WebVueStorefrontTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_web_shop_vue_storefront.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE,
            checker=doctest_checker))
    return suite
