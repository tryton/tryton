# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from werkzeug.exceptions import abort
from werkzeug.wrappers import Response

from trytond.wsgi import app
from trytond.protocols.wrappers import with_pool, with_transaction


@app.route(
    '/<database_name>/account_payment_stripe/checkout/<model>/<id>',
    methods=['GET', 'POST'])
@with_pool
@with_transaction()
def checkout(request, pool, model, id):
    Payment = pool.get('account.payment')
    Customer = pool.get('account.payment.stripe.customer')
    ContactMechanism = pool.get('party.contact_mechanism')
    if model == Payment.__name__:
        Model = Payment
    elif model == Customer.__name__:
        Model = Customer
    else:
        abort(403)
    try:
        record, = Model.search([
                ('stripe_checkout_id', '=', id),
                ])
    except ValueError:
        abort(403)
    if request.method == 'GET':
        Report = pool.get('account.payment.stripe.checkout', type='report')
        # TODO language
        data = {
            'model': Model.__name__,
            }
        ext, content, _, _ = Report.execute([record.id], data)
        assert ext == 'html'
        return Response(content, 200, content_type='text/html')
    elif request.method == 'POST':
        record.stripe_token = request.form['stripeToken']
        record.save()
        email = request.form.get('stripeEmail')
        if email:
            for mechanism in record.party.contact_mechanisms:
                if mechanism.type == 'email' and mechanism.value == email:
                    break
            else:
                mechanism = ContactMechanism(
                    type='email', value=email, party=record.party)
                mechanism.save()
        return Response(
            '<body onload="window.close()">', 200, content_type='text/html')
