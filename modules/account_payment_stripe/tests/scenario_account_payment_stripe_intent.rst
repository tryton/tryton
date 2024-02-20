======================================
Account Payment Stripe Intent Scenario
======================================

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

    >>> FETCH_SLEEP, MAX_SLEEP = 1, 100

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
    >>> party = Party(name='Customer')
    >>> party.save()

Register card::

    >>> Cron = Model.get('ir.cron')
    >>> Customer = Model.get('account.payment.stripe.customer')
    >>> customer = Customer()
    >>> customer.party = party
    >>> customer.stripe_account = stripe_account
    >>> customer.save()

    >>> _ = customer.click('stripe_checkout')
    >>> payment_method = stripe.PaymentMethod.create(
    ...     type='card',
    ...     card={
    ...         'number': '4000000000003055',
    ...         'exp_month': 12,
    ...         'exp_year': datetime.date.today().year + 1,
    ...         'cvc': '123',
    ...         })
    >>> setup_intent = stripe.SetupIntent.confirm(
    ...     customer.stripe_setup_intent_id,
    ...     return_url='http://localhost/',
    ...     payment_method=payment_method)
    >>> cron_update_intent, = Cron.find([
    ...     ('method', '=', 'account.payment.stripe.customer|stripe_intent_update'),
    ...     ])
    >>> cron_update_intent.companies.append(Company(company.id))
    >>> cron_update_intent.click('run_once')
    >>> customer.reload()
    >>> bool(customer.stripe_customer_id)
    True

Create approved payment::

    >>> Payment = Model.get('account.payment')
    >>> payment = Payment()
    >>> payment.journal = payment_journal
    >>> payment.kind = 'receivable'
    >>> payment.party = party
    >>> payment.amount = Decimal('42')
    >>> payment.description = 'Testing'
    >>> payment.stripe_customer = customer
    >>> payment.stripe_customer_payment_method = payment_method.id
    >>> payment.click('approve')
    >>> payment.state
    'approved'

Process off-session the payment::

    >>> process_payment = Wizard('account.payment.process', [payment])
    >>> process_payment.execute('process')
    >>> payment.state
    'processing'

    >>> for _ in range(MAX_SLEEP):
    ...     cron_fetch_events.click('run_once')
    ...     payment.reload()
    ...     if payment.state == 'succeeded':
    ...         break
    ...     time.sleep(FETCH_SLEEP)
    >>> payment.state
    'succeeded'
    >>> bool(payment.stripe_captured)
    True

Refund the payment::

    >>> Refund = Model.get('account.payment.stripe.refund')
    >>> refund = Refund()
    >>> refund.payment = payment
    >>> refund.amount = payment.amount
    >>> refund.click('approve')
    >>> cron_refund_create, = Cron.find([
    ...     ('method', '=', 'account.payment.stripe.refund|stripe_create'),
    ...     ])
    >>> cron_refund_create.click('run_once')

    >>> for _ in range(MAX_SLEEP):
    ...     cron_fetch_events.click('run_once')
    ...     payment.reload()
    ...     if payment.state == 'failed':
    ...         break
    ...     time.sleep(FETCH_SLEEP)
    >>> payment.state
    'failed'

Cancel payment intent::

    >>> payment = Payment()
    >>> payment.journal = payment_journal
    >>> payment.kind = 'receivable'
    >>> payment.party = party
    >>> payment.amount = Decimal('42')
    >>> payment.description = 'Testing canceled'
    >>> payment.stripe_customer = customer
    >>> payment.stripe_customer_payment_method = payment_method.id
    >>> payment.stripe_capture = False
    >>> payment.click('approve')
    >>> payment.state
    'approved'

    >>> process_payment = Wizard('account.payment.process', [payment])
    >>> process_payment.execute('process')
    >>> payment.state
    'processing'

    >>> _ = stripe.PaymentIntent.cancel(payment.stripe_payment_intent_id)

    >>> for _ in range(MAX_SLEEP):
    ...     cron_fetch_events.click('run_once')
    ...     payment.reload()
    ...     if payment.state == 'failed':
    ...         break
    ...     time.sleep(FETCH_SLEEP)
    >>> payment.state
    'failed'
