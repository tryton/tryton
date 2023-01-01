================================
Account Payment Stripe Identical
================================

Imports::

    >>> import datetime as dt
    >>> import os
    >>> import time
    >>> from decimal import Decimal

    >>> import stripe

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules('account_payment_stripe')

    >>> Company = Model.get('company.company')
    >>> Cron = Model.get('ir.cron')
    >>> StripeAccount = Model.get('account.payment.stripe.account')
    >>> StripeCustomer = Model.get('account.payment.stripe.customer')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create Stripe account::

    >>> stripe_account = StripeAccount(name="Stripe")
    >>> stripe_account.secret_key = os.getenv('STRIPE_SECRET_KEY')
    >>> stripe_account.publishable_key = os.getenv('STRIPE_PUBLISHABLE_KEY')
    >>> stripe_account.save()
    >>> stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

Setup cron::

    >>> cron_customer_create, = Cron.find([
    ...     ('method', '=', 'account.payment.stripe.customer|stripe_create'),
    ...     ])
    >>> cron_customer_create.companies.append(Company(company.id))
    >>> cron_customer_create.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer1 = Party(name="Customer 1")
    >>> customer1.save()

    >>> customer2 = Party(name="Customer 2")
    >>> customer2.save()

Create a customer::

    >>> stripe_customer1 = StripeCustomer()
    >>> stripe_customer1.party = customer1
    >>> stripe_customer1.stripe_account = stripe_account
    >>> _ = stripe_customer1.click('stripe_checkout')
    >>> token = stripe.Token.create(
    ...     card={
    ...         'number': '4012888888881881',
    ...         'exp_month': 12,
    ...         'exp_year': today.year + 1,
    ...         'cvc': '123',
    ...         },
    ...     )
    >>> StripeCustomer.write(
    ...     [stripe_customer1.id], {'stripe_token': token.id}, config.context)

Run cron::

    >>> cron_customer_create.click('run_once')

    >>> stripe_customer1.reload()
    >>> stripe_customer1.identical_customers
    []

Create a second customer with same card::

    >>> stripe_customer2 = StripeCustomer()
    >>> stripe_customer2.party = customer2
    >>> stripe_customer2.stripe_account = stripe_account
    >>> _ = stripe_customer2.click('stripe_checkout')
    >>> token = stripe.Token.create(
    ...     card={
    ...         'number': '4012888888881881',
    ...         'exp_month': 12,
    ...         'exp_year': today.year + 1,
    ...         'cvc': '123',
    ...         },
    ...     )
    >>> StripeCustomer.write(
    ...     [stripe_customer2.id], {'stripe_token': token.id}, config.context)

Run cron::

    >>> cron_customer_create.click('run_once')

    >>> stripe_customer2.reload()
    >>> stripe_customer2.identical_customers == [stripe_customer1]
    True
    >>> stripe_customer1.reload()
    >>> stripe_customer1.identical_customers == [stripe_customer2]
    True
