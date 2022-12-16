# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from http import HTTPStatus
except ImportError:
    from http import client as HTTPStatus

from werkzeug.utils import redirect
from werkzeug.exceptions import abort

from trytond.protocols.wrappers import with_pool, with_transaction
from trytond.wsgi import app


@app.route('/s/<base64:database_name>$<shortened>')
@with_pool
@with_transaction(readonly=False)
def shortened(request, pool, shortened):
    ShortenedURL = pool.get('web.shortened_url')

    try:
        shortened_url = ShortenedURL.get(shortened)
    except IndexError:
        abort(HTTPStatus.NOT_FOUND)

    return redirect(shortened_url.access(), code=301)
