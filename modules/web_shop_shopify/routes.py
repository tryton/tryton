# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import base64
import hashlib
import hmac
import logging

from trytond.protocols.wrappers import (
    HTTPStatus, Response, abort, with_pool, with_transaction)
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
    elif topic in {'orders/updated', 'orders/payment'}:
        sales = Sale.search([
                ('web_shop', '=', shop.id),
                ('shopify_identifier', '=', order['id']),
                ], order=[], limit=1)
        if not sales:
            Shop.__queue__.shopify_fetch_order([shop])
        else:
            sale, = sales
            Shop.__queue__.shopify_update_sale([sale], [order])
    else:
        logger.info("Unsupported topic '%s'", topic)
    return Response(status=HTTPStatus.NO_CONTENT)
