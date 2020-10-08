==================================
Account Payment Braintree Scenario
==================================

Imports::

    >>> import os
    >>> import random
    >>> from decimal import Decimal
    >>> import braintree
    >>> from braintree.test.nonces import Nonces
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts

Activate modules::

    >>> config = activate_modules('account_payment_braintree')

Get cron::

    >>> Cron = Model.get('ir.cron')

Create company::

    >>> Company = Model.get('company.company')
    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = create_fiscalyear(company)
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)

Create Braintree account::

    >>> BraintreeAccount = Model.get('account.payment.braintree.account')
    >>> braintree_account = BraintreeAccount(name="Braintree")
    >>> braintree_account.currency = company.currency
    >>> braintree_account.environment = 'sandbox'
    >>> braintree_account.merchant_id = os.getenv('BRAINTREE_MERCHANT_ID')
    >>> braintree_account.public_key = os.getenv('BRAINTREE_PUBLIC_KEY')
    >>> braintree_account.private_key = os.getenv('BRAINTREE_PRIVATE_KEY')
    >>> braintree_account.save()

    >>> gateway = braintree.BraintreeGateway(braintree.Configuration(
    ...         environment=braintree.Environment.Sandbox,
    ...         merchant_id=braintree_account.merchant_id,
    ...         public_key=braintree_account.public_key,
    ...         private_key=braintree_account.private_key,
    ...         ))

Create webhook identifier::

    >>> braintree_account.click('new_identifier')
    >>> len(braintree_account.webhook_identifier)
    32

Remove webhook::

    >>> braintree_account.click('new_identifier')
    >>> braintree_account.webhook_identifier

Create payment journal::

    >>> PaymentJournal = Model.get('account.payment.journal')
    >>> payment_journal = PaymentJournal(name="Braintree",
    ...     process_method='braintree', braintree_account=braintree_account)
    >>> payment_journal.save()

Create party::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name="Customer")
    >>> customer.save()

Create approved payment::

    >>> Payment = Model.get('account.payment')
    >>> payment = Payment()
    >>> payment.journal = payment_journal
    >>> payment.kind = 'receivable'
    >>> payment.party = customer
    >>> # Use random amount to prevent gateway rejection for duplicate
    >>> payment.amount = amount = Decimal(random.randint(0, 1999))
    >>> payment.click('approve')
    >>> payment.state
    'approved'

Checkout the payment::

    >>> action_id = payment.click('braintree_checkout')
    >>> checkout = Wizard('account.payment.braintree.checkout', [payment])
    >>> bool(payment.braintree_checkout_id)
    True

    >>> Payment.write([payment.id], {
    ...     'braintree_nonce': Nonces.Transactable,
    ...     }, config.context)

Process the payment::

    >>> process_payment = Wizard('account.payment.process', [payment])
    >>> process_payment.execute('process')
    >>> payment.state
    'processing'
    >>> bool(payment.braintree_payment_settled)
    True
    >>> payment.amount == amount
    True

    >>> _ = gateway.testing.settle_transaction(payment.braintree_transaction_id)

Pull update::

    >>> cron_payment_pull, = Cron.find([
    ...     ('method', '=', 'account.payment|braintree_pull'),
    ...     ])
    >>> cron_payment_pull.companies.append(Company(company.id))
    >>> cron_payment_pull.click('run_once')

    >>> payment.reload()
    >>> payment.state
    'succeeded'
    >>> payment.amount == amount
    True

Create a customer::

    >>> Customer = Model.get('account.payment.braintree.customer')
    >>> braintree_customer = Customer()
    >>> braintree_customer.party = customer
    >>> braintree_customer.braintree_account = braintree_account
    >>> braintree_customer.save()
    >>> Customer.write([braintree_customer.id], {
    ...     'braintree_nonce': Nonces.Transactable,
    ...     }, config.context)

Run cron::

    >>> cron_customer_create, = Cron.find([
    ...     ('method', '=', 'account.payment.braintree.customer|braintree_create'),
    ...     ])
    >>> cron_customer_create.companies.append(Company(company.id))
    >>> cron_customer_create.click('run_once')

    >>> braintree_customer.reload()
    >>> bool(braintree_customer.braintree_customer_id)
    True

Make payment with customer::

    >>> payment, = payment.duplicate()
    >>> payment.braintree_customer = braintree_customer
    >>> payment.amount = amount = Decimal(random.randint(0, 1999))
    >>> payment.save()
    >>> _, method = Payment.get_braintree_customer_methods(payment.id, config.context)
    >>> method_token, _ = method
    >>> payment.braintree_customer_method = method_token
    >>> payment.click('approve')
    >>> payment.state
    'approved'
    >>> process_payment = Wizard('account.payment.process', [payment])
    >>> process_payment.execute('process')
    >>> payment.state
    'processing'

    >>> _ = gateway.testing.settle_transaction(payment.braintree_transaction_id)
    >>> cron_payment_pull.click('run_once')
    >>> payment.reload()
    >>> payment.state
    'succeeded'

Delete customer::

    >>> braintree_customer.delete()
    >>> bool(braintree_customer.active)
    False

Run cron::

    >>> cron_customer_delete, = Cron.find([
    ...     ('method', '=', 'account.payment.braintree.customer|braintree_delete'),
    ...     ])
    >>> cron_customer_delete.companies.append(Company(company.id))
    >>> cron_customer_delete.click('run_once')

    >>> braintree_customer.reload()
    >>> braintree_customer.braintree_customer_id

Create payment to settle::

    >>> payment, = payment.duplicate()
    >>> payment.braintree_customer = None
    >>> payment.braintree_settle_payment = False
    >>> payment.amount = amount = Decimal(random.randint(0, 1999))
    >>> payment.click('approve')
    >>> payment.state
    'approved'

    >>> Payment.write([payment.id], {
    ...     'braintree_nonce': Nonces.Transactable,
    ...     }, config.context)

    >>> process_payment = Wizard('account.payment.process', [payment])
    >>> process_payment.execute('process')
    >>> payment.state
    'processing'

    >>> _ = gateway.testing.settle_transaction(payment.braintree_transaction_id)
    >>> cron_payment_pull.click('run_once')
    >>> payment.reload()
    >>> payment.state
    'processing'

Settle lower amount::

    >>> payment.amount = amount = Decimal(random.randint(2, int(payment.amount)))
    >>> payment.click('braintree_do_settle_payment')
    >>> payment.state
    'processing'

    >>> _ = gateway.testing.settle_transaction(payment.braintree_transaction_id)
    >>> cron_payment_pull.click('run_once')
    >>> payment.reload()
    >>> payment.state
    'succeeded'
    >>> bool(payment.braintree_payment_settled)
    True

Refund some amount::

    >>> Refund = Model.get('account.payment.braintree.refund')
    >>> refund = Refund()
    >>> refund.payment = payment
    >>> refund.amount = amount - 1
    >>> refund.click('approve')
    >>> cron_refund, = Cron.find([
    ...     ('method', '=', 'account.payment.braintree.refund|braintree_refund'),
    ...     ])
    >>> cron_refund.companies.append(Company(company.id))
    >>> cron_refund.click('run_once')

    >>> refund.reload()
    >>> refund.state
    'processing'
    >>> payment.reload()
    >>> payment.amount == amount
    True

    >>> _ = gateway.testing.settle_transaction(refund.braintree_transaction_id)
    >>> cron_refund_pull, = Cron.find([
    ...     ('method', '=', 'account.payment.braintree.refund|braintree_pull'),
    ...     ])
    >>> cron_refund_pull.companies.append(Company(company.id))
    >>> cron_refund_pull.click('run_once')
    >>> refund.reload()
    >>> refund.state
    'succeeded'

    >>> payment.reload()
    >>> payment.amount
    Decimal('1.00')
    >>> payment.state
    'succeeded'

Try to refund more::

    >>> refund = Refund()
    >>> refund.payment = payment
    >>> refund.amount = Decimal('10')
    >>> refund.click('approve')
    >>> cron_refund.click('run_once')
    >>> refund.reload()
    >>> refund.state
    'failed'
    >>> payment.reload()
    >>> payment.amount
    Decimal('1.00')
