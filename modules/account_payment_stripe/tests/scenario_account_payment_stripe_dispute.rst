=======================================
Account Payment Stripe Dispute Scenario
=======================================

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
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create fully disputed payment::

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

    >>> _ = payment.click('stripe_checkout')
    >>> checkout = Wizard('account.payment.stripe.checkout', [payment])
    >>> bool(payment.stripe_checkout_id)
    True

    >>> token = stripe.Token.create(
    ...     card={
    ...         'number': '4000000000000259',
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

Simulate charge.dispute.created event::

    >>> StripeAccount.webhook([stripe_account], {
    ...         'type': 'charge.dispute.created',
    ...         'data': {
    ...             'object': {
    ...                 'object': 'dispute',
    ...                 'charge': payment.stripe_charge_id,
    ...                 'amount': 4200,
    ...                 'currency': 'usd',
    ...                 'reason': 'customer_initiated',
    ...                 'status': 'needs_response',
    ...                 },
    ...             },
    ...         }, {})
    [True]
    >>> payment.reload()
    >>> payment.state
    'succeeded'
    >>> payment.stripe_dispute_reason
    'customer_initiated'
    >>> payment.stripe_dispute_status
    'needs_response'

Simulate charge.dispute.closed event::

    >>> StripeAccount.webhook([stripe_account], {
    ...         'type': 'charge.dispute.closed',
    ...         'data': {
    ...             'object': {
    ...                 'object': 'dispute',
    ...                 'charge': payment.stripe_charge_id,
    ...                 'amount': 4200,
    ...                 'currency': 'usd',
    ...                 'reason': 'customer_initiated',
    ...                 'status': 'lost',
    ...                 },
    ...             },
    ...         }, {})
    [True]
    >>> payment.reload()
    >>> payment.state
    'failed'
    >>> payment.stripe_dispute_reason
    'customer_initiated'
    >>> payment.stripe_dispute_status
    'lost'

Create partial disputed payment::

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

    >>> _ = payment.click('stripe_checkout')
    >>> checkout = Wizard('account.payment.stripe.checkout', [payment])
    >>> bool(payment.stripe_checkout_id)
    True

    >>> token = stripe.Token.create(
    ...     card={
    ...         'number': '4000000000000259',
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

Simulate charge.dispute.closed event::

    >>> StripeAccount.webhook([stripe_account], {
    ...         'type': 'charge.dispute.closed',
    ...         'data': {
    ...             'object': {
    ...                 'object': 'dispute',
    ...                 'charge': payment.stripe_charge_id,
    ...                 'amount': 1200,
    ...                 'currency': 'usd',
    ...                 'reason': 'general',
    ...                 'status': 'lost',
    ...                 },
    ...             },
    ...         }, {})
    [True]
    >>> payment.reload()
    >>> payment.state
    'succeeded'
    >>> payment.amount
    Decimal('30.00')
    >>> payment.stripe_dispute_reason
    'general'
    >>> payment.stripe_dispute_status
    'lost'

Create won disputed payment::

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

    >>> _ = payment.click('stripe_checkout')
    >>> checkout = Wizard('account.payment.stripe.checkout', [payment])
    >>> bool(payment.stripe_checkout_id)
    True

    >>> token = stripe.Token.create(
    ...     card={
    ...         'number': '4000000000000259',
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

Simulate charge.dispute.closed event::

    >>> charge = stripe.Charge.retrieve(payment.stripe_charge_id)
    >>> dispute = stripe.Dispute.modify(charge.dispute,
    ...     evidence={'uncategorized_text': 'winning_evidence'})

    >>> for _ in range(MAX_SLEEP):
    ...     cron_fetch_events.click('run_once')
    ...     payment.reload()
    ...     if payment.stripe_dispute_status == 'won':
    ...         break
    ...     time.sleep(FETCH_SLEEP)
    >>> payment.state
    'succeeded'
    >>> payment.amount
    Decimal('42.00')
    >>> payment.stripe_dispute_reason
    'fraudulent'
    >>> payment.stripe_dispute_status
    'won'
