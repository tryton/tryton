# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import base64
import hashlib
import hmac
import logging

from trytond.protocols.wrappers import (
    HTTPStatus, Response, abort, redirect, with_pool, with_transaction)
from trytond.wsgi import app

logger = logging.getLogger(__name__)


def verify_webhook(data, hmac_header, secret):
    digest = hmac.new(secret, data, hashlib.sha256).digest()
    computed_hmac = base64.b64encode(digest)
    return hmac.compare_digest(computed_hmac, hmac_header.encode('utf-8'))


@app.route(
    '/<database_name>/web_shop_shopify/webhook/<shop>/order', methods={'POST'})
@with_pool
@with_transaction(context={'_skip_warnings': True})
def order(request, pool, shop):
    Sale = pool.get('sale.sale')
    Shop = pool.get('web.shop')
    shop = Shop.get(shop)
    data = request.get_data()
    verified = verify_webhook(
        data, request.headers.get('X-Shopify-Hmac-SHA256'),
        shop.shopify_webhook_shared_secret.encode('utf-8'))
    if not verified:
        abort(HTTPStatus.UNAUTHORIZED)

    topic = request.headers.get('X-Shopify-Topic')
    order = request.get_json()
    if topic == 'orders/create':
        if not Sale.search([
                    ('web_shop', '=', shop.id),
                    ('shopify_identifier', '=', order['id']),
                    ], order=[], limit=1):
            Shop.__queue__.shopify_fetch_order([shop])
    elif topic in {
            'orders/updated', 'orders/edited', 'orders/paid',
            'orders/cancelled'}:
        if topic == 'orders/edited':
            order_id = order['order_edit']['id']
        else:
            order_id = order['id']
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
        logger.info("Unsupported topic '%s'", topic)
    return Response(status=HTTPStatus.NO_CONTENT)


@app.route('/<database_name>/web_shop_shopify/products/<id>', methods={'GET'})
@app.auth_required
@with_pool
@with_transaction(user='request')
def shopify_product(request, pool, id):
    Template = pool.get('product.template')
    try:
        template, = Template.search(
            [('shopify_identifiers.shopify_identifier_char', '=', id)],
            limit=1)
    except ValueError:
        abort(HTTPStatus.NOT_FOUND)
    return redirect(template.__href__)


@app.route(
    '/<database_name>/web_shop_shopify'
    '/products/<product_id>/variants/<variant_id>',
    methods={'GET'})
@app.auth_required
@with_pool
@with_transaction(user='request')
def shopify_product_variant(request, pool, product_id, variant_id):
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


@app.route('/<database_name>/web_shop_shopify/customers/<id>', methods={'GET'})
@app.auth_required
@with_pool
@with_transaction(user='request')
def shopify_customer(request, pool, id):
    Party = pool.get('party.party')
    try:
        party, = Party.search([
                ('shopify_identifiers.shopify_identifier_char', '=', id),
                ], limit=1)
    except ValueError:
        abort(HTTPStatus.NOT_FOUND)
    return redirect(party.__href__)


@app.route('/<database_name>/web_shop_shopify/orders/<id>', methods={'GET'})
@app.auth_required
@with_pool
@with_transaction(user='request')
def shopify_order(request, pool, id):
    Sale = pool.get('sale.sale')
    try:
        sale, = Sale.search([('shopify_identifier_char', '=', id)], limit=1)
    except ValueError:
        abort(HTTPStatus.NOT_FOUND)
    return redirect(sale.__href__)
