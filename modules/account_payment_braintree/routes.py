# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import http.client
import logging

from trytond.protocols.wrappers import (
    HTTPStatus, Response, abort, with_pool, with_transaction)
from trytond.routing import Route, Router, Rule

logger = logging.getLogger(__name__)


class Braintree(Router):
    __name__ = 'account_payment_braintree'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__routes__.update({
                'checkout': Route(
                    Rule('checkout/<model>/<id>', methods={'GET', 'POST'}),
                    decorators=[
                        with_pool,
                        with_transaction(context={'_skip_warnings': True}),
                        ]),
                'webhooks_endpoint': Route(
                    Rule('webhook/<account>', methods={'POST'}),
                    Rule('/<database_name>/account_payment_braintree/'
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
            Report = pool.get(
                'account.payment.braintree.checkout', type='report')
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
            if model == Payment.__name__:
                Payment.process([record])
            return Response(
                '<body onload="window.close();"></body>',
                HTTPStatus.OK,
                content_type='text/html')

    @classmethod
    def webhooks_endpoint(cls, request, pool, account):
        from braintree import exceptions
        Account = pool.get('account.payment.braintree.account')
        account, = Account.search([
                ('webhook_identifier', '=', account),
                ])
        gateway = account.gateway()
        try:
            notification = gateway.webhook_notification.parse(
                str(request.form['bt_signature']), request.form['bt_payload'])
        except exceptions.invalid_signature_error.InvalidSignatureError:
            abort(http.client.BAD_REQUEST)

        result = account.webhook(notification)
        if result is None:
            logger.info(
                "No callback for notification kind '%s'", notification.kind)
        elif not result:
            return Response(status=http.client.NOT_FOUND)
        return Response(status=http.client.NO_CONTENT)
