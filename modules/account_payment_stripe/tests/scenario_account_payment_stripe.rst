===============================
Account Payment Stripe Scenario
===============================

Imports::

    >>> import os
    >>> import datetime
    >>> import time
    >>> from decimal import Decimal
    >>> import stripe
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts

Activate modules::

    >>> config = activate_modules('account_payment_stripe')

Create company::

    >>> Company = Model.get('company.company')
    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = create_fiscalyear(company)
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)

Create Stripe account::

    >>> StripeAccount = Model.get('account.payment.stripe.account')
    >>> stripe_account = StripeAccount(name="Stripe")
    >>> stripe_account.secret_key = os.getenv('STRIPE_SECRET_KEY')
    >>> stripe_account.publishable_key = os.getenv('STRIPE_PUBLISHABLE_KEY')
    >>> stripe_account.save()
    >>> stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

Create webhook identifier::

    >>> stripe_account.click('new_identifier')
    >>> len(stripe_account.webhook_identifier)
    32

Remove webhook::

    >>> stripe_account.click('new_identifier')
    >>> stripe_account.webhook_identifier

Setup fetch events cron::

    >>> Cron = Model.get('ir.cron')
    >>> cron_fetch_events, = Cron.find([
    ...     ('method', '=', 'account.payment.stripe.account|fetch_events'),
    ...     ])
    >>> cron_fetch_events.companies.append(Company(company.id))

Create payment journal::

    >>> PaymentJournal = Model.get('account.payment.journal')
    >>> payment_journal = PaymentJournal(name="Stripe",
    ...     process_method='stripe', stripe_account=stripe_account)
    >>> payment_journal.save()

Create party::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create approved payment::

    >>> Payment = Model.get('account.payment')
    >>> payment = Payment()
    >>> payment.journal = payment_journal
    >>> payment.kind = 'receivable'
    >>> payment.party = customer
    >>> payment.amount = Decimal('42')
    >>> payment.description = 'Testing'
    >>> payment.click('approve')
    >>> payment.state
    'approved'

Checkout the payment::

    >>> action_id = payment.click('stripe_checkout')
    >>> checkout = Wizard('account.payment.stripe.checkout', [payment])
    >>> bool(payment.stripe_checkout_id)
    True

    >>> token = stripe.Token.create(
    ...     card={
    ...         'number': '4242424242424242',
    ...         'exp_month': 12,
    ...         'exp_year': datetime.date.today().year + 1,
    ...         'cvc': '123',
    ...         },
    ...     )
    >>> Payment.write([payment.id], {
    ...     'stripe_token': token.id,
    ...     'stripe_chargeable': True,
    ...     'stripe_payment_intent_id': None,  # Remove intent from checkout
    ...     }, config.context)

Process the payment::

    >>> process_payment = Wizard('account.payment.process', [payment])
    >>> process_payment.execute('process')
    >>> payment.state
    'processing'

    >>> time.sleep(1)
    >>> cron_fetch_events.click('run_once')
    >>> payment.reload()
    >>> payment.state
    'succeeded'
    >>> bool(payment.stripe_captured)
    True

Create failing payment::

    >>> previous_idempotency_key = payment.stripe_idempotency_key
    >>> payment, = payment.duplicate()
    >>> payment.stripe_idempotency_key != previous_idempotency_key
    True
    >>> payment.click('approve')
    >>> payment.state
    'approved'
    >>> action_id = payment.click('stripe_checkout')
    >>> checkout = Wizard('account.payment.stripe.checkout', [payment])
    >>> bool(payment.stripe_checkout_id)
    True
    >>> token = stripe.Token.create(
    ...     card={
    ...         'number': '4000000000000002',
    ...         'exp_month': 12,
    ...         'exp_year': datetime.date.today().year + 1,
    ...         'cvc': '123',
    ...         },
    ...     )
    >>> Payment.write([payment.id], {
    ...     'stripe_token': token.id,
    ...     'stripe_chargeable': True,
    ...     'stripe_payment_intent_id': None,  # Remove intent from checkout
    ...     }, config.context)
    >>> process_payment = Wizard('account.payment.process', [payment])
    >>> process_payment.execute('process')
    >>> payment.state
    'failed'
    >>> payment.stripe_error_code
    'card_declined'

Create a customer::

    >>> Customer = Model.get('account.payment.stripe.customer')
    >>> stripe_customer = Customer()
    >>> stripe_customer.party = customer
    >>> stripe_customer.stripe_account = stripe_account

Checkout the customer::

    >>> action_id = stripe_customer.click('stripe_checkout')
    >>> checkout = Wizard('account.payment.stripe.checkout', [stripe_customer])
    >>> bool(stripe_customer.stripe_checkout_id)
    True

    >>> token = stripe.Token.create(
    ...     card={
    ...         'number': '4012888888881881',
    ...         'exp_month': 12,
    ...         'exp_year': datetime.date.today().year + 1,
    ...         'cvc': '123',
    ...         },
    ...     )
    >>> Customer.write(
    ...     [stripe_customer.id], {'stripe_token': token.id}, config.context)

Run cron::

    >>> cron_customer_create, = Cron.find([
    ...     ('method', '=', 'account.payment.stripe.customer|stripe_create'),
    ...     ])
    >>> cron_customer_create.companies.append(Company(company.id))
    >>> cron_customer_create.click('run_once')

    >>> stripe_customer.reload()
    >>> bool(stripe_customer.stripe_customer_id)
    True

Make payment with customer::

    >>> payment, = payment.duplicate()
    >>> payment.stripe_customer = stripe_customer
    >>> payment.save()
    >>> _, source = Payment.get_stripe_customer_sources(payment.id, config.context)
    >>> source_id, source_name = source
    >>> source_name == 'Visa ****1881 12/%s' % (datetime.date.today().year + 1)
    True
    >>> payment.stripe_customer_source = source_id
    >>> payment.click('approve')
    >>> payment.state
    'approved'
    >>> process_payment = Wizard('account.payment.process', [payment])
    >>> process_payment.execute('process')
    >>> payment.state
    'processing'

    >>> time.sleep(1)
    >>> cron_fetch_events.click('run_once')
    >>> payment.reload()
    >>> payment.state
    'succeeded'

Detach source::

    >>> detach = Wizard(
    ...     'account.payment.stripe.customer.source.detach', [stripe_customer])
    >>> detach.form.source = source_id
    >>> detach.execute('detach')

    >>> cus = stripe.Customer.retrieve(stripe_customer.stripe_customer_id)
    >>> len(cus.sources)
    0
    >>> len(stripe.PaymentMethod.list(customer=cus.id, type='card'))
    0

Delete customer::

    >>> stripe_customer.delete()
    >>> bool(stripe_customer.active)
    False

Run cron::

    >>> cron_customer_delete, = Cron.find([
    ...     ('method', '=', 'account.payment.stripe.customer|stripe_delete'),
    ...     ])
    >>> cron_customer_delete.companies.append(Company(company.id))
    >>> cron_customer_delete.click('run_once')

    >>> stripe_customer.reload()
    >>> stripe_customer.stripe_token
    >>> stripe_customer.stripe_customer_id

Create capture payment::

    >>> payment, = payment.duplicate()
    >>> payment.stripe_capture = False
    >>> payment.click('approve')
    >>> payment.state
    'approved'

Checkout the capture payment::

    >>> token = stripe.Token.create(
    ...     card={
    ...         'number': '4242424242424242',
    ...         'exp_month': 12,
    ...         'exp_year': datetime.date.today().year + 1,
    ...         'cvc': '123',
    ...         },
    ...     )
    >>> Payment.write([payment.id], {
    ...     'stripe_token': token.id,
    ...     }, config.context)

Process the capture payment::

    >>> process_payment = Wizard('account.payment.process', [payment])
    >>> process_payment.execute('process')
    >>> payment.state
    'processing'
    >>> bool(payment.stripe_captured)
    False

Capture lower amount::

    >>> payment.amount = Decimal('40')
    >>> payment.click('stripe_do_capture')
    >>> payment.state
    'processing'

    >>> time.sleep(1)
    >>> cron_fetch_events.click('run_once')
    >>> payment.reload()
    >>> payment.state
    'succeeded'
    >>> bool(payment.stripe_captured)
    True

Refund some amount::

    >>> Refund = Model.get('account.payment.stripe.refund')
    >>> refund = Refund()
    >>> refund.payment = payment
    >>> refund.amount = Decimal('38')
    >>> refund.click('approve')
    >>> cron_refund_create, = Cron.find([
    ...     ('method', '=', 'account.payment.stripe.refund|stripe_create'),
    ...     ])
    >>> cron_refund_create.click('run_once')
    >>> cron_fetch_events.click('run_once')

    >>> payment.reload()
    >>> payment.amount
    Decimal('2.00')
    >>> payment.state
    'succeeded'
    >>> refund.reload()
    >>> refund.state
    'succeeded'

Simulate charge.refunded event with full amount::

    >>> refund = Refund()
    >>> refund.payment = payment
    >>> refund.amount = Decimal('2')
    >>> refund.click('approve')
    >>> cron_refund_create.click('run_once')
    >>> cron_fetch_events.click('run_once')

    >>> payment.reload()
    >>> payment.amount
    Decimal('0.00')
    >>> payment.state
    'failed'
    >>> refund.reload()
    >>> refund.state
    'succeeded'

Try to refund more::

    >>> refund = Refund()
    >>> refund.payment = payment
    >>> refund.amount = Decimal('10')
    >>> refund.click('approve')
    >>> cron_refund_create.click('run_once')
    >>> cron_fetch_events.click('run_once')
    >>> refund.reload()
    >>> refund.state
    'failed'
