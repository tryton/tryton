# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import json

import trytond.config as config
from trytond.protocols.wrappers import (
    HTTPStatus, Response, abort, set_max_request_size, with_pool,
    with_transaction)
from trytond.routing import Route, Router, Rule


class InboundEmail(Router):
    __name__ = 'inbound_email'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__routes__.update({
                'inbound_email': Route(
                    Rule('inbox/<identifier>', methods={'POST'}),
                    Rule('/<database_name>/inbound_email/'
                        'inbox/<identifier>', methods={'POST'},
                        redirect_to='inbox/<identifier>'),
                    decorators=[
                        set_max_request_size(
                            config.getint(
                                'inbound_email', 'max_size',
                                default=config.getint('request', 'max_size'))),
                        with_pool,
                        with_transaction(),
                        ]),
                })

    @classmethod
    def inbound_email(cls, request, pool, identifier):
        Inbox = pool.get('inbound.email.inbox')
        Email = pool.get('inbound.email')

        try:
            inbox, = Inbox.search([
                    ('identifier', '=', identifier),
                    ])
        except ValueError:
            abort(HTTPStatus.NOT_FOUND)

        data_type = request.args.get('type', 'raw')

        if request.form:
            data = json.dumps(request.form.to_dict()).encode()
        else:
            data = request.data
        emails = Email.from_webhook(inbox, data, data_type)
        if not emails:
            abort(HTTPStatus.BAD_REQUEST)
        for email in emails:
            inbox.process(email)
        Email.save(emails)
        return Response(status=HTTPStatus.NO_CONTENT)
