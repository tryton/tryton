=====================================
Account Payment Stripe Refund Failure
=====================================

Imports::

    >>> import datetime as dt
    >>> import os
    >>> import time
    >>> from decimal import Decimal

    >>> import stripe

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import create_chart, create_fiscalyear
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules

    >>> today = dt.date.today()
    >>> FETCH_SLEEP, MAX_SLEEP = 1, 100

Activate modules::

    >>> config = activate_modules(
    ...     'account_payment_stripe', create_company, create_chart)

    >>> Cron = Model.get('ir.cron')
    >>> Payment = Model.get('account.payment')
    >>> Refund = Model.get('account.payment.stripe.refund')
    >>> StripeAccount = Model.get('account.payment.stripe.account')

Create fiscal year::

    >>> fiscalyear = create_fiscalyear(today=today)
    >>> fiscalyear.click('create_period')

Create Stripe account::

    >>> stripe_account = StripeAccount(name="Stripe")
    >>> stripe_account.secret_key = os.getenv('STRIPE_SECRET_KEY')
    >>> stripe_account.publishable_key = os.getenv('STRIPE_PUBLISHABLE_KEY')
    >>> stripe_account.save()
    >>> stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

Setup fetch events cron::

    >>> cron_fetch_events, = Cron.find([
    ...     ('method', '=', 'account.payment.stripe.account|fetch_events'),
    ...     ])
    >>> cron_fetch_events.companies.append(get_company())

Create payment journal::

    >>> PaymentJournal = Model.get('account.payment.journal')
    >>> payment_journal = PaymentJournal(name="Stripe",
    ...     process_method='stripe', stripe_account=stripe_account)
    >>> payment_journal.save()

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name="Customer")
    >>> party.save()

Submit a payment::

    >>> payment = Payment()
    >>> payment.journal = payment_journal
    >>> payment.kind = 'receivable'
    >>> payment.party = party
    >>> payment.amount = Decimal('42')
    >>> payment.reference = "Testing"
    >>> payment.click('submit')
    >>> payment.state
    'submitted'

Checkout the payment::

    >>> token = stripe.Token.create(
    ...     card={
    ...         'number': '4000000000005126',  # async refund failure
    ...         'exp_month': 12,
    ...         'exp_year': today.year + 1,
    ...         'cvc': '123',
    ...         },
    ...     )
    >>> Payment.write([payment.id], {
    ...     'stripe_token': token.id,
    ...     'stripe_chargeable': True,
    ...     }, config.context)

Process the payment::

    >>> process_payment = payment.click('process_wizard')
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

Refund some amount::

    >>> refund = Refund()
    >>> refund.payment = payment
    >>> refund.amount = Decimal('12')
    >>> refund.click('submit')
    >>> refund.click('approve')
    >>> refund.state
    'approved'

    >>> cron_refund_create, = Cron.find([
    ...     ('method', '=', 'account.payment.stripe.refund|stripe_create'),
    ...     ])
    >>> cron_refund_create.click('run_once')

    >>> refund.reload()
    >>> refund.state
    'succeeded'

    >>> for _ in range(MAX_SLEEP):
    ...     cron_fetch_events.click('run_once')
    ...     refund.reload()
    ...     if refund.state == 'failed':
    ...         break
    ...     time.sleep(FETCH_SLEEP)
    >>> refund.reload()
    >>> refund.state
    'failed'
    >>> payment.reload()
    >>> payment.amount
    Decimal('42.00')
    >>> payment.state
    'succeeded'
