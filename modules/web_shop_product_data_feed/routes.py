# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.protocols.wrappers import send_file, with_pool, with_transaction
from trytond.routing import Route, Router, Rule


class ProductDataFeed(Router):
    __name__ = 'web_shop'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__routes__.update({
                'product_data_feed': Route(
                    Rule('<shop>/<format>/products.csv', methods={'GET'}),
                    Rule('/<database_name>/web_shop/'
                        '<shop>/<format>/products.csv', methods={'GET'},
                        redirect_to='<shop>/<format>/products.csv'),
                    Rule(
                        '<shop>/<format>/<language>/products.csv',
                        methods={'GET'}),
                    Rule('/<database_name>/web_shop/'
                        '<shop>/<format>/<language>/products.csv',
                        methods={'GET'},
                        redirect_to='<shop>/<format>/<language>/products.csv'),
                    decorators=[
                        with_pool,
                        with_transaction(),
                        ]),
                })

    @classmethod
    def product_data_feed(cls, request, pool, shop, format, language=None):
        Shop = pool.get('web.shop')
        shop = Shop.get(shop)

        file = shop.product_data_feed_csv(format, language)

        return send_file(
            file, request.environ, as_attachment=True, mimetype='text/csv',
            download_name='products.csv')
