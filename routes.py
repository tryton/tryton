# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from werkzeug.wrappers import Response
from werkzeug.utils import redirect

from trytond.transaction import Transaction
from trytond.tools import file_open
from trytond.protocols.wrappers import with_pool, with_transaction
from trytond.wsgi import app


@app.route('/m/<base64:database_name>$unsubscribe')
@with_pool
@with_transaction(readonly=False)
def unsubscribe(request, pool):
    Record = pool.get('marketing.automation.record')
    Report = pool.get('marketing.automation.unsubscribe', type='report')
    record, = Record.search([
            ('uuid', '=', request.args['r']),
            ])
    record.block()
    next_ = request.args.get('next')
    if next_:
        redirect(next_)
    data = {
        'model': Record.__name__,
        }
    with Transaction().set_context(language=record.language):
        ext, content, _, _ = Report.execute([record], data)
    assert ext == 'html'
    return Response(content, 200, content_type='text/html')


@app.route('/m/empty.gif')
def empty(request):
    fp = file_open('marketing_automation/empty.gif', mode='rb')
    return Response(fp, 200, content_type='image/gif', direct_passthrough=True)
