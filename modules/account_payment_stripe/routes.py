# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import json
import logging

import stripe

from trytond.protocols.wrappers import (
    HTTPStatus, Response, abort, with_pool, with_transaction)
from trytond.wsgi import app

logger = logging.getLogger(__name__)


@app.route(
    '/<database_name>/account_payment_stripe/checkout/<model>/<id>',
    methods=['GET'])
@with_pool
@with_transaction(context={'_skip_warnings': True})
def checkout(request, pool, model, id):
    Payment = pool.get('account.payment')
    Customer = pool.get('account.payment.stripe.customer')
    if model == Payment.__name__:
        Model = Payment
    elif model == Customer.__name__:
        Model = Customer
    else:
        abort(HTTPStatus.FORBIDDEN)
    try:
        record, = Model.search([
                ('stripe_checkout_id', '=', id),
                ])
    except ValueError:
        abort(HTTPStatus.NOT_FOUND)
    customer_session_client_secret = ''
    if model == Payment.__name__ and record.stripe_customer:
        if customer_session := record.stripe_customer.get_session():
            customer_session_client_secret = customer_session.client_secret
    Report = pool.get('account.payment.stripe.checkout', type='report')
    # TODO language
    data = {
        'model': Model.__name__,
        'customer_session_client_secret': customer_session_client_secret,
        'return_url': request.base_url + '/end'
        }
    ext, content, _, _ = Report.execute([record.id], data)
    assert ext == 'html'
    return Response(content, HTTPStatus.OK, content_type='text/html')


@app.route(
    '/<database_name>/account_payment_stripe/checkout/<model>/<id>/end',
    methods=['GET'])
@with_pool
@with_transaction(readonly=False, context={'_skip_warnings': True})
def checkout_end(request, pool, model, id):
    Payment = pool.get('account.payment')
    Customer = pool.get('account.payment.stripe.customer')
    if model == Payment.__name__:
        Model = Payment
    elif model == Customer.__name__:
        Model = Customer
    else:
        abort(HTTPStatus.FORBIDDEN)
    try:
        record, = Model.search([
                ('stripe_checkout_id', '=', id),
                ])
    except ValueError:
        abort(HTTPStatus.NOT_FOUND)
    if model == Payment.__name__:
        Payment.process([record])
    record.stripe_intent_update()
    return Response(
        '<body onload="window.close()">', HTTPStatus.OK,
        content_type='text/html')


@app.route(
    '/<database_name>/account_payment_stripe/webhook/<account>',
    methods={'POST'})
@with_pool
@with_transaction(context={'_skip_warnings': True})
def webhooks_endpoint(request, pool, account):
    Account = pool.get('account.payment.stripe.account')
    account, = Account.search([
            ('webhook_identifier', '=', account),
            ])

    if account.webhook_signing_secret:
        sig_header = request.headers['STRIPE_SIGNATURE']
        request_body = request.get_data(as_text=True)
        try:
            stripe.Webhook.construct_event(
                request_body, sig_header, account.webhook_signing_secret)
        except ValueError:  # Invalid payload
            abort(HTTPStatus.BAD_REQUEST)
        except stripe.SignatureVerificationError:
            abort(HTTPStatus.BAD_REQUEST)
    else:
        logger.warn("Stripe signature ignored")

    payload = json.loads(request_body)
    result = account.webhook(payload)
    if result is None:
        logger.info("No callback for payload type '%s'", payload['type'])
    elif not result:
        return Response(status=HTTPStatus.NOT_FOUND)
    return Response(status=HTTPStatus.NO_CONTENT)
