# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.protocols.wrappers import send_file, with_pool, with_transaction
from trytond.wsgi import app


@app.route(
    '/<database_name>/web_shop/<shop>/<format>/<language>/products.csv',
    methods={'GET'})
@app.route(
    '/<database_name>/web_shop/<shop>/<format>/products.csv',
    methods={'GET'})
@with_pool
@with_transaction()
def product_data_feed(request, pool, shop, format, language=None):
    Shop = pool.get('web.shop')
    shop = Shop.get(shop)

    file = shop.product_data_feed_csv(format, language)

    return send_file(
        file, request.environ, as_attachment=True, mimetype='text/csv',
        download_name='products.csv')
