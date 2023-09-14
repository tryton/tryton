# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import base64

from trytond.protocols.wrappers import (
    HTTPStatus, Response, abort, user_application, with_pool, with_transaction)
from trytond.wsgi import app

document_incoming_application = user_application('document_incoming')


@app.route('/<database_name>/document_incoming', methods=['POST'])
@with_pool
@with_transaction()
@document_incoming_application
def document_incoming(request, pool):
    Document = pool.get('document.incoming')

    def convert_boolean(value):
        try:
            return bool(int(value))
        except ValueError:
            abort(HTTPStatus.BAD_REQUEST)

    if isinstance(request.parsed_data, dict):
        values = request.parsed_data.copy()
        values['data'] = base64.b64decode(values.get('data', b''))
    else:
        values = request.args.to_dict()
        values['data'] = request.data

    values.setdefault('name', 'data.bin')

    fields = {n for n, f in Document._fields.items() if not f.readonly}
    for extra in values.keys() - fields:
        del values[extra]

    document = Document(**values)
    document.save()

    if convert_boolean(request.args.get('process', False)) and document.type:
        Document.process([document], with_children=True)
    return Response(status=HTTPStatus.NO_CONTENT)
