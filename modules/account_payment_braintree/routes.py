# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import http.client
import logging
try:
    from http import HTTPStatus
except ImportError:
    from http import client as HTTPStatus

import braintree
from werkzeug.exceptions import abort
from werkzeug.wrappers import Response

from trytond.protocols.wrappers import with_pool, with_transaction
from trytond.wsgi import app

logger = logging.getLogger(__name__)


@app.route(
    '/<database_name>/account_payment_braintree/checkout/<model>/<id>',
    methods=['GET', 'POST'])
@with_pool
@with_transaction()
def checkout(request, pool, model, id):
    Payment = pool.get('account.payment')
    Customer = pool.get('account.payment.braintree.customer')
    if model == Payment.__name__:
        Model = Payment
    elif model == Customer.__name__:
        Model = Customer
    else:
        abort(HTTPStatus.FORBIDDEN)
    try:
        record, = Model.search([
                ('braintree_checkout_id', '=', id),
                ])
    except ValueError:
        abort(HTTPStatus.FORBIDDEN)
    if request.method == 'GET':
        Report = pool.get('account.payment.braintree.checkout', type='report')
        # TODO language
        data = {
            'model': Model.__name__,
            'client_token': record.braintree_client_token,
            }
        ext, content, _, _ = Report.execute([record.id], data)
        assert ext == 'html'
        return Response(content, HTTPStatus.OK, content_type='text/html')
    elif request.method == 'POST':
        record.braintree_set_nonce(
            request.form['payment_method_nonce'],
            request.form.get('device_data'))
        return Response(
            '<body onload="window.close();"></body>',
            HTTPStatus.OK,
            content_type='text/html')


@app.route(
    '/<database_name>/account_payment_braintree/webhook/<account>',
    methods={'POST'})
@with_pool
@with_transaction()
def webhooks_endpoint(request, pool, account):
    Account = pool.get('account.payment.braintree.account')
    account, = Account.search([
            ('webhook_identifier', '=', account),
            ])
    gateway = account.gateway()
    try:
        notification = gateway.webhook_notification.parse(
            str(request.form['bt_signature']), request.form['bt_payload'])
    except braintree.exceptions.invalid_signature_error.InvalidSignatureError:
        abort(http.client.BAD_REQUEST)

    result = account.webhook(notification)
    if result is None:
        logger.info(
            "No callback for notification kind '%s'", notification.kind)
    elif not result:
        return Response(status=http.client.NOT_FOUND)
    return Response(status=http.client.NO_CONTENT)
