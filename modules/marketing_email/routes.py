# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from werkzeug.wrappers import Response

from trytond.tools import file_open
from trytond.wsgi import app


@app.route('/m/empty.gif')
def empty(request):
    fp = file_open('marketing_email/empty.gif', mode='rb')
    return Response(fp, 200, content_type='image/gif', direct_passthrough=True)
