# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import json
import logging

from trytond import config
from trytond.protocols.wrappers import (
    HTTPStatus, Response, abort, set_max_request_size, with_pool,
    with_transaction)
from trytond.wsgi import app

logger = logging.getLogger(__name__)


@app.route(
    '/<database_name>/edocument_peppol_peppyrus/<identifier>/in',
    methods={'POST'})
@set_max_request_size(config.getint(
        'edocument_peppol_peppyrus', 'max_size',
        default=config.getint('request', 'max_size')))
@with_pool
@with_transaction()
def incoming(request, pool, identifier):
    Service = pool.get('edocument.peppol.service')

    try:
        service, = Service.search([
                ('peppyrus_identifier', '=', identifier),
                ])
    except ValueError:
        abort(HTTPStatus.NOT_FOUND)

    request_body = request.get_data(as_text=True)
    message = json.loads(request_body)
    Service.peppyrus_store(message)
    return Response(status=HTTPStatus.NO_CONTENT)


@app.route(
    '/<database_name>/edocument_peppol_peppyrus/<identifier>/out',
    methods={'POST'})
@set_max_request_size(config.getint(
        'edocument_peppol_peppyrus', 'max_size',
        default=config.getint('request', 'max_size')))
@with_pool
@with_transaction()
def outgoing(request, pool, identifier):
    Service = pool.get('edocument.peppol.service')
    Document = pool.get('edocument.peppol')

    try:
        service, = Service.search([
                ('peppyrus_identifier', '=', identifier),
                ])
    except ValueError:
        abort(HTTPStatus.NOT_FOUND)

    request_body = request.get_data(as_text=True)
    message = json.loads(request_body)
    document, = Document.search([
            ('service', '=', service),
            ('transmission_id', '=', message['id']),
            ])
    service.peppyrus_update(document, message)
    return Response(status=HTTPStatus.NO_CONTENT)
