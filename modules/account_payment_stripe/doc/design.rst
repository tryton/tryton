******
Design
******

The *Account Payment Stripe Module* introduces and extends the following
concepts:

.. _model-account.payment:

Payment
=======

When the *Account Payment Stripe Module* is activated, the *Payment* gains new
properties used to store the Stripe information from processing payments where
the process method of the `Payment Journal
<account_payment:model-account.payment.journal>` is :guilabel:`Stripe`.

A Stripe payment can be processed using a token_, a source_, or a `payment
method`_ from the `Customer <model-account.payment.stripe.customer>`.
In the case a payment is processed off-session and requires authorization, an
email is sent to the `Party <party:model-party.party>` with a link to the
checkout form.
If an error occurs, the error message from Stripe is collected and displayed.

The :guilabel:`Capture` box can be unchecked so the payment is only authorized
when processed.
The payment is then captured later.

A `scheduled task <trytond:model-ir.cron>` runs every 15 minutes to charge each
processing payment.
There is another that also runs every 15 minutes to capture the payments.

If a payment is disputed, it is only updated when the dispute is closed.

The Stripe payments also have a :guilabel:`Stripe Pull` button which can be
used to force an update with the stripe charges.

.. seealso::

   The `Payment <account_payment:model-account.payment>` concept is introduced
   by the :doc:`Account Payment Module <account_payment:index>`.

.. _token: https://docs.stripe.com/api/tokens
.. _source: https://docs.stripe.com/sources
.. _payment method: https://docs.stripe.com/payments/payment-methods

.. _model-account.payment.stripe.refund:

Stripe Payment Refund
=====================

The *Stripe Payment Refund* represents an order to refund some amount of a
`Payment <model-account.payment>`.

Once processed, a payment refund can not be changed.

.. seealso::

   The Stripe Payment Refunds can be found by opening the main menu item:

   |Financial --> Payments --> Stripe Refunds|__

   .. |Financial --> Payments --> Stripe Refunds| replace:: :menuselection:`Financial --> Payments --> Stripe Refunds`
   __ https://demo.tryton.org/model/account.payment.stripe.refund

.. _model-account.payment.journal:

Payment Journal
===============

When the *Account Payment Stripe Module* is activated, the *Payment Journal*
gains a property for the `Stripe Account
<model-account.payment.stripe.account>` for those journals where the processing
method is :guilabel:`Stripe`.

.. seealso::

   The `Payment Journal <account_payment:model-account.payment.journal>`
   concept is introduced by the :doc:`Account Payment Module
   <account_payment:index>`.

.. _model-account.payment.stripe.account:

Stripe Account
==============

The *Stripe Account* stores the credentials needed to communicate with the
Stripe API.

It also displays the URL to set up on Stripe for the webhooks_.
For additional security, the signature from Stripe's requests can be verified
if the :guilabel:`Webhook Signing Secret` is set.

.. note::
   If no webhooks are set up, a `scheduled task <trytond:model-ir.cron>` is run
   every 15 minutes to fetch new events.

.. seealso::

   The Stripe Accounts can be found by opening the main menu item:

   |Financial --> Configuration --> Payments --> Stripe Accounts|__

   .. |Financial --> Configuration --> Payments --> Stripe Accounts| replace:: :menuselection:`Financial --> Configuration --> Payments --> Stripe Accounts`
   __ https://demo.tryton.org/model/account.payment.stripe.account

.. _webhooks: https://docs.stripe.com/webhooks

.. _model-account.payment.stripe.customer:

Stripe Customer
===============

The *Stripe Customer* links a `Party <party:model-party.party>` to a `Stripe
customer`_.

A `scheduled task <trytond:model-ir.cron>` runs every hour to create new
customers on Stripe and another to delete them if they have become inactivate.

.. seealso::

   The Stripe Customers can be found by opening the main menu item:

   |Financial --> Payments --> Stripe Customers|__

   .. |Financial --> Payments --> Stripe Customers| replace:: :menuselection:`Financial --> Payments --> Stripe Customers`
   __ https://demo.tryton.org/model/account.payment.stripe.customer

.. _Stripe customer: https://docs.stripe.com/api/customers

.. _report-account.payment.stripe.checkout:

Stripe Checkout
===============

The *Stripe Checkout* report renders an :abbr:`HTML (Hypertext Markup
Language)` document using the Stripe Javascript library to display a checkout
form for `Payments <model-account.payment>` or `Stripe Customers
<model-account.payment.stripe.customer>`.
