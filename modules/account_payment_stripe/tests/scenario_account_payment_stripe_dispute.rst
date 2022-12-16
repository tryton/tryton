=======================================
Account Payment Stripe Dispute Scenario
=======================================

Imports::

    >>> import os
    >>> import datetime
    >>> from decimal import Decimal
    >>> import stripe
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts

Install account_payment_stripe::

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
    u'approved'

    >>> _ = payment.click('stripe_checkout')
    >>> checkout = Wizard('account.payment.stripe.checkout', [payment])
    >>> bool(payment.stripe_checkout_id)
    True

    >>> token = stripe.Token.create(
    ...     api_key=payment.journal.stripe_account.secret_key,
    ...     card={
    ...         'number': '4000000000000259',
    ...         'exp_month': 12,
    ...         'exp_year': datetime.date.today().year + 1,
    ...         'cvc': '123',
    ...         },
    ...     )
    >>> payment.stripe_token = token.id
    >>> payment.stripe_chargeable = True
    >>> payment.save()

    >>> process_payment = Wizard('account.payment.process', [payment])
    >>> process_payment.execute('process')
    >>> payment.state
    u'processing'

    >>> Cron = Model.get('ir.cron')
    >>> cron_charge, = Cron.find([
    ...         ('model', '=', 'account.payment'),
    ...         ('function', '=', 'stripe_charge'),
    ...         ])
    >>> cron_charge.companies.append(Company(company.id))
    >>> cron_charge.click('run_once')

    >>> payment.reload()
    >>> payment.state
    u'succeeded'
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
    u'succeeded'
    >>> payment.stripe_dispute_reason
    u'customer_initiated'
    >>> payment.stripe_dispute_status
    u'needs_response'

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
    u'failed'
    >>> payment.stripe_dispute_reason
    u'customer_initiated'
    >>> payment.stripe_dispute_status
    u'lost'

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
    u'approved'

    >>> _ = payment.click('stripe_checkout')
    >>> checkout = Wizard('account.payment.stripe.checkout', [payment])
    >>> bool(payment.stripe_checkout_id)
    True

    >>> token = stripe.Token.create(
    ...     api_key=payment.journal.stripe_account.secret_key,
    ...     card={
    ...         'number': '4000000000000259',
    ...         'exp_month': 12,
    ...         'exp_year': datetime.date.today().year + 1,
    ...         'cvc': '123',
    ...         },
    ...     )
    >>> payment.stripe_token = token.id
    >>> payment.stripe_chargeable = True
    >>> payment.save()

    >>> process_payment = Wizard('account.payment.process', [payment])
    >>> process_payment.execute('process')
    >>> payment.state
    u'processing'

    >>> Cron = Model.get('ir.cron')
    >>> cron_charge, = Cron.find([
    ...         ('model', '=', 'account.payment'),
    ...         ('function', '=', 'stripe_charge'),
    ...         ])
    >>> cron_charge.companies.append(Company(company.id))
    >>> cron_charge.click('run_once')

    >>> payment.reload()
    >>> payment.state
    u'succeeded'
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
    u'succeeded'
    >>> payment.amount
    Decimal('30.00')
    >>> payment.stripe_dispute_reason
    u'general'
    >>> payment.stripe_dispute_status
    u'lost'

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
    u'approved'

    >>> _ = payment.click('stripe_checkout')
    >>> checkout = Wizard('account.payment.stripe.checkout', [payment])
    >>> bool(payment.stripe_checkout_id)
    True

    >>> token = stripe.Token.create(
    ...     api_key=payment.journal.stripe_account.secret_key,
    ...     card={
    ...         'number': '4000000000000259',
    ...         'exp_month': 12,
    ...         'exp_year': datetime.date.today().year + 1,
    ...         'cvc': '123',
    ...         },
    ...     )
    >>> payment.stripe_token = token.id
    >>> payment.stripe_chargeable = True
    >>> payment.save()

    >>> process_payment = Wizard('account.payment.process', [payment])
    >>> process_payment.execute('process')
    >>> payment.state
    u'processing'

    >>> Cron = Model.get('ir.cron')
    >>> cron_charge, = Cron.find([
    ...         ('model', '=', 'account.payment'),
    ...         ('function', '=', 'stripe_charge'),
    ...         ])
    >>> cron_charge.companies.append(Company(company.id))
    >>> cron_charge.click('run_once')

    >>> payment.reload()
    >>> payment.state
    u'succeeded'
    >>> bool(payment.stripe_captured)
    True

Simulate charge.dispute.closed event::

    >>> StripeAccount.webhook([stripe_account], {
    ...         'type': 'charge.dispute.closed',
    ...         'data': {
    ...             'object': {
    ...                 'object': 'dispute',
    ...                 'charge': payment.stripe_charge_id,
    ...                 'amount': 4200,
    ...                 'currency': 'usd',
    ...                 'reason': 'general',
    ...                 'status': 'won',
    ...                 },
    ...             },
    ...         }, {})
    [True]
    >>> payment.reload()
    >>> payment.state
    u'succeeded'
    >>> payment.amount
    Decimal('42')
    >>> payment.stripe_dispute_reason
    u'general'
    >>> payment.stripe_dispute_status
    u'won'
