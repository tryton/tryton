# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from urllib.parse import unquote

import trytond.config as config
from trytond.protocols.wrappers import (
    HTTPStatus, Response, abort, with_pool, with_transaction)
from trytond.wsgi import app


@app.route(
    '/product/image/<code>/<base64:database_name>',
    methods={'GET'})
@app.route(
    '/product/image/<code>/<base64:database_name>/<name>',
    methods={'GET'})
@with_pool
@with_transaction()
def product_image(request, pool, code, name=None):
    Template = pool.get('product.template')
    try:
        template, = Template.search([
                ('code', '=', unquote(code)),
                ])
    except ValueError:
        abort(HTTPStatus.NOT_FOUND)
    return _image(request, pool, template)


@app.route(
    '/product/variant/image/<code>/<base64:database_name>',
    methods={'GET'})
@app.route(
    '/product/variant/image/<code>/<base64:database_name>/<name>',
    methods={'GET'})
@with_pool
@with_transaction()
def variant_image(request, pool, code, name=None):
    Product = pool.get('product.product')
    try:
        product, = Product.search([
                ('code', '=', unquote(code)),
                ])
    except ValueError:
        abort(HTTPStatus.NOT_FOUND)
    return _image(request, pool, product)


@app.route(
    '/product-category/image/<code>/<base64:database_name>',
    methods={'GET'})
@app.route(
    '/product-category/image/<code>/<base64:database_name>/<name>',
    methods={'GET'})
@with_pool
@with_transaction()
def category_image(request, pool, code, name=None):
    Category = pool.get('product.category')
    try:
        category, = Category.search([
                ('code', '=', unquote(code)),
                ])
    except ValueError:
        abort(HTTPStatus.NOT_FOUND)
    return _image(request, pool, category)


def _image(request, pool, record):
    images = record.get_images(request.args)
    if not images:
        abort(HTTPStatus.NOT_FOUND)
    try:
        image = list(images)[int(request.args.get('i', 0))]
    except IndexError:
        abort(HTTPStatus.NOT_FOUND)
    except ValueError:
        abort(HTTPStatus.BAD_REQUEST)
    try:
        size = int(request.args.get('s', 400))
    except ValueError:
        abort(HTTPStatus.BAD_REQUEST)
    try:
        width = int(request.args.get('w', size))
    except ValueError:
        abort(HTTPStatus.BAD_REQUEST)
    try:
        height = int(request.args.get('h', size))
    except ValueError:
        abort(HTTPStatus.BAD_REQUEST)

    response = Response(image.get((width, height)), mimetype='image/jpeg')
    response.headers['Cache-Control'] = (
        'max-age=%s, public' % config.getint(
            'product', 'image_timeout', default=365 * 24 * 60 * 60))
    response.add_etag()
    return response
