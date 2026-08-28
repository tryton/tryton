# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import json
import logging

from trytond.protocols.wrappers import (
    HTTPStatus, Response, abort, with_pool, with_transaction)
from trytond.routing import Route, Router, Rule

logger = logging.getLogger(__name__)


class Stripe(Router):
    __name__ = 'account_payment_stripe'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__routes__.update({
                'checkout': Route(
                    Rule('checkout/<model>/<id>', methods={'GET'}),
                    decorators=[
                        with_pool,
                        with_transaction(context={'_skip_warnings': True}),
                        ]),
                'checkout_end': Route(
                    Rule('checkout/<model>/<id>/end', methods={'GET'}),
                    decorators=[
                        with_pool,
                        with_transaction(
                            readonly=False,
                            context={'_skip_warnings': True}),
                        ]),
                'webhooks_endpoint': Route(
                    Rule('webhook/<account>', methods={'POST'}),
                    Rule('/<database_name>/account_payment_stripe/'
                        'webhook/<account>', methods={'POST'},
                        redirect_to='webhook/<account>'),
                    decorators=[
                        with_pool,
                        with_transaction(context={'_skip_warnings': True}),
                        ]),
                })

    @classmethod
    def checkout(cls, request, pool, model, id):
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

    @classmethod
    def checkout_end(cls, request, pool, model, id):
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

    @classmethod
    def webhooks_endpoint(cls, request, pool, account):
        import stripe
        Account = pool.get('account.payment.stripe.account')
        account, = Account.search([
                ('webhook_identifier', '=', account),
                ])

        request_body = request.get_data(as_text=True)
        if account.webhook_signing_secret:
            sig_header = request.headers['STRIPE_SIGNATURE']
            try:
                event = stripe.Webhook.construct_event(
                    request_body, sig_header, account.webhook_signing_secret)
            except ValueError:  # Invalid payload
                abort(HTTPStatus.BAD_REQUEST)
            except stripe.SignatureVerificationError:
                abort(HTTPStatus.BAD_REQUEST)
        else:
            logger.warn("Stripe signature ignored")
            try:
                event = stripe.Event.construct_from(
                    json.loads(request_body), account.secret_key)
            except ValueError:
                abort(HTTPStatus.BAD_REQUEST)

        result = account.webhook(event)
        if result is None:
            logger.info("No callback for event type '%s'", event['type'])
        elif not result:
            return Response(status=HTTPStatus.NOT_FOUND)
        return Response(status=HTTPStatus.NO_CONTENT)
