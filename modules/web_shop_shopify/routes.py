# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import logging

from shopify_app import RequestInput, verify_webhook_req

from trytond.protocols.wrappers import (
    HTTPStatus, Response, abort, redirect, with_pool, with_transaction)
from trytond.routing import Route, Router, Rule
from trytond.wsgi import app

logger = logging.getLogger(__name__)


def request_to_shopify_req(request):
    return RequestInput(
        method=request.method,
        headers=dict(request.headers),
        url=request.url,
        body=request.get_data(as_text=True, parse_form_data=True))


class Shopify(Router):
    __name__ = 'web_shop_shopify'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__routes__.update({
                'webhook_order': Route(
                    Rule('webhook/<shop>/order', methods={'POST'}),
                    Rule('/<database_name>/web_shop_shopify/'
                        'webhook/<shop>/order', methods={'POST'},
                        redirect_to='webhook/<shop>/order'),
                    decorators=[
                        with_pool,
                        with_transaction(context={'_skip_warnings': True}),
                        ]),
                'product': Route(
                    Rule('products/<id>', methods={'GET'}),
                    Rule('/<database_name>/web_shop_shopify/'
                        'products/<id>', methods={'GET'},
                        redirect_to='products/<id>'),
                    decorators=[
                        app.auth_required,
                        with_pool,
                        with_transaction(user='request'),
                        ]),
                'product_variant': Route(
                    Rule(
                        'products/<product_id>/variants/<variant_id>',
                        methods={'GET'}),
                    Rule('/<database_name>/web_shop_shopify/'
                        'products/<product_id>/variants/<variant_id>',
                        methods={'GET'},
                        redirect_to=(
                            'products/<product_id>/variants/<variant_id>')),
                    decorators=[
                        app.auth_required,
                        with_pool,
                        with_transaction(user='request'),
                        ]),
                'customer': Route(
                    Rule('customers/<id>', methods={'GET'}),
                    Rule('/<database_name>/web_shop_shopify/'
                        'customers/<id>', methods={'GET'},
                        redirect_to='customers/<id>'),
                    decorators=[
                        app.auth_required,
                        with_pool,
                        with_transaction(user='request'),
                        ]),
                'shopify_order': Route(
                    Rule('orders/<id>', methods={'GET'}),
                    Rule('/<database_name>/web_shop_shopify/'
                        'orders/<id>', methods={'GET'},
                        redirect_to='orders/<id>'),
                    decorators=[
                        app.auth_required,
                        with_pool,
                        with_transaction(user='request'),
                        ]),
                })

    @classmethod
    def webhook_order(cls, request, pool, shop):
        Sale = pool.get('sale.sale')
        Shop = pool.get('web.shop')
        shop = Shop.get(shop)

        result = verify_webhook_req(
            request_to_shopify_req(request), {
                'client_secret': shop.shopify_webhook_shared_secret,
                })
        if not result.ok:
            logger.debug("unauthorized %s", result)
            abort(result.response.status, result.response.body)

        topic = request.headers.get('X-Shopify-Topic')
        order = request.get_json()
        if topic == 'orders/edited':
            order_id = order['order_edit']['id']
        else:
            order_id = order['id']
        logger.info("Shopify webhook %s for %s", topic, order_id)
        if topic == 'orders/create':
            if not Sale.search([
                        ('web_shop', '=', shop.id),
                        ('shopify_identifier', '=', order_id),
                        ], order=[], limit=1):
                Shop.__queue__.shopify_fetch_order([shop])
        elif topic in {
                'orders/updated', 'orders/edited', 'orders/paid',
                'orders/cancelled'}:
            sales = Sale.search([
                    ('web_shop', '=', shop.id),
                    ('shopify_identifier', '=', order_id),
                    ], order=[], limit=1)
            if not sales:
                Shop.__queue__.shopify_fetch_order([shop])
            else:
                sale, = sales
                Shop.__queue__.update_sale_ids(shop, [sale.id])
        else:
            logger.warn("Unsupported topic '%s'", topic)
        return Response(status=HTTPStatus.NO_CONTENT)

    @classmethod
    def product(cls, request, pool, id):
        Template = pool.get('product.template')
        try:
            template, = Template.search(
                [('shopify_identifiers.shopify_identifier_char', '=', id)],
                limit=1)
        except ValueError:
            abort(HTTPStatus.NOT_FOUND)
        return redirect(template.__href__)

    @classmethod
    def product_variant(cls, request, pool, product_id, variant_id):
        Product = pool.get('product.product')
        try:
            product, = Product.search([
                    ('template.shopify_identifiers.shopify_identifier_char',
                        '=', product_id),
                    ('shopify_identifiers.shopify_identifier_char',
                        '=', variant_id),
                    ],
                limit=1)
        except ValueError:
            abort(HTTPStatus.NOT_FOUND)
        return redirect(product.__href__)

    @classmethod
    def customer(cls, request, pool, id):
        Party = pool.get('party.party')
        try:
            party, = Party.search([
                    ('shopify_identifiers.shopify_identifier_char', '=', id),
                    ], limit=1)
        except ValueError:
            abort(HTTPStatus.NOT_FOUND)
        return redirect(party.__href__)

    @classmethod
    def shopify_order(cls, request, pool, id):
        Sale = pool.get('sale.sale')
        try:
            sale, = Sale.search(
                [('shopify_identifier_char', '=', id)],
                limit=1)
        except ValueError:
            abort(HTTPStatus.NOT_FOUND)
        return redirect(sale.__href__)
