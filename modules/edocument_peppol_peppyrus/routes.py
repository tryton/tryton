# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import json
import logging

from trytond import config
from trytond.protocols.wrappers import (
    HTTPStatus, Response, abort, set_max_request_size, with_pool,
    with_transaction)
from trytond.routing import Route, Router, Rule

logger = logging.getLogger(__name__)


class PeppolPeppyrus(Router):
    __name__ = 'edocument_peppol_peppyrus'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__routes__.update({
                'incoming': Route(
                    Rule('<identifier>/in', methods={'POST'}),
                    Rule('/<database_name>/edocument_peppol_peppyrus/'
                        '<identifier>/in', methods={'POST'},
                        redirect_to='<identifier>/in'),
                    decorators=[
                        set_max_request_size(
                            config.getint(
                                'edocument_peppol_peppyrus', 'max_size',
                                default=config.getint('request', 'max_size'))),
                        with_pool,
                        with_transaction(),
                        ]),
                'outgoing': Route(
                    Rule('<identifier>/out', methods={'POST'}),
                    Rule('/<database_name>/edocument_peppol_peppyrus/'
                        '<identifier>/out', methods={'POST'},
                        redirect_to='<identifier>/out'),
                    decorators=[
                        set_max_request_size(
                            config.getint(
                                'edocument_peppol_peppyrus', 'max_size',
                                default=config.getint('request', 'max_size'))),
                        with_pool,
                        with_transaction(),
                        ]),
                })

    @classmethod
    def incoming(cls, request, pool, identifier):
        Service = pool.get('edocument.peppol.service')

        try:
            service, = Service.search([
                    ('peppyrus_identifier', '=', identifier),
                    ])
        except ValueError:
            abort(HTTPStatus.NOT_FOUND)

        message = json.loads(request.data)
        Service.peppyrus_store(message)
        return Response(status=HTTPStatus.NO_CONTENT)

    @classmethod
    def outgoing(cls, request, pool, identifier):
        Service = pool.get('edocument.peppol.service')
        Document = pool.get('edocument.peppol')

        try:
            service, = Service.search([
                    ('peppyrus_identifier', '=', identifier),
                    ])
        except ValueError:
            abort(HTTPStatus.NOT_FOUND)

        message = json.loads(request.data)
        document, = Document.search([
                ('service', '=', service),
                ('transmission_id', '=', message['id']),
                ])
        service.peppyrus_update(document, message)
        return Response(status=HTTPStatus.NO_CONTENT)
