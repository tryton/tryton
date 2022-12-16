# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging

from werkzeug.exceptions import HTTPException

from trytond import backend
from trytond.exceptions import UserError, UserWarning
from trytond.protocols.wrappers import with_pool, with_transaction
from trytond.transaction import Transaction
from trytond.wsgi import app

logger = logging.getLogger(__name__)


@app.route(
    '/<database_name>/web_shop_vue_storefront/<shop>/<target>/<action>',
    methods={'POST', 'GET'})
@app.route(
    '/<database_name>/web_shop_vue_storefront/<shop>/<target>/<action>/<sku>',
    methods={'GET'})
@with_pool
@with_transaction(context={'_skip_warnings': True})
def route(request, pool, shop, target, action, sku=None):
    Shop = pool.get('web.shop')
    Session = pool.get('web.user.session')
    shop = Shop.get(shop)
    method = '_'.join(
        [request.method, 'vsf', target, action.replace('-', '_')])
    if 'token' in request.args:
        with Transaction().new_transaction():
            try:
                Session.reset(request.args['token'])
            except backend.DatabaseOperationalError:
                logger.debug('Reset session failed', exc_info=True)
    try:
        if request.data:
            data = request.parsed_data
        else:
            data = None
        kwargs = request.args.to_dict()
        if sku is not None:
            kwargs['sku'] = sku
        with Transaction().set_context(**shop.get_context()):
            result = getattr(shop, method)(data, **kwargs)
    except HTTPException as exception:
        Transaction().rollback()
        return {'code': exception.code, 'result': exception.description}
    except (UserError, UserWarning) as exception:
        Transaction().rollback()
        return {'code': '400', 'result': str(exception)}
    except Exception as exception:
        Transaction().rollback()
        return {'code': 500, 'result': str(exception)}
    return {'code': 200, 'result': result}
