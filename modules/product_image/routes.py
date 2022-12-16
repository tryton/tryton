# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
try:
    from http import HTTPStatus
except ImportError:
    from http import client as HTTPStatus

from urllib.parse import unquote

from werkzeug.exceptions import abort
from werkzeug.wrappers import Response

from trytond.config import config
from trytond.protocols.wrappers import with_pool, with_transaction
from trytond.wsgi import app

TIMEOUT = config.getint('product', 'image_timeout', default=365 * 24 * 60 * 60)


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
    response = Response(image.get(size), mimetype='image/jpeg')
    response.headers['Cache-Control'] = (
        'max-age=%s, public' % TIMEOUT)
    response.add_etag()
    return response
