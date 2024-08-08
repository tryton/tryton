******
Design
******

The *Account Payment Braintree Module* introduces and extends the following
concepts:

.. _model-account.payment:

Payment
=======

When the *Account Payment Braintree Module* is activated, the *Payment* gains
new properties used to store the Braintree information from processing payments
where the process method of the `Payment Journal
<account_payment:model-account.payment.journal>` is :guilabel:`Braintree`.

A Braintree payment can be processed using a nonce or a `payment method`_ from
the `Customer <model-account.payment.braintree.customer>`.
In case of an error, the error message from Braintree is collected and
displayed.
The settle field can be unchecked to only authorize the payment during
processing and then to settle the amount in a second step.

Two `scheduled tasks <trytond:model-ir.cron>` run every 15 minutes to transact
and settle each processing payment.
Another scheduled task also runs every 15 minutes to pull updates for each
processing payment until they have succeeded or failed.
The Braintree payments also have a :guilabel:`Braintree Pull` button which can
be used to force an update using the braintree transaction.

.. seealso::

   The `Payment <account_payment:model-account.payment>` concept is introduced
   by the :doc:`Account Payment Module <account_payment:index>`.

.. _payment method: https://developers.braintreepayments.com/guides/payment-methods

.. _model-account.payment.braintree.refund:

Braintree Payment Refund
========================

The *Braintree Payment Refund* represents an order to refund some amount of a
`Payment <model-account.payment>`.

Once processed, a payment refund can not be changed.

.. seealso::

   The Braintree payment refund can be found by opening the main menu item:

   |Financial --> Payments --> Braintree Refunds|__

   .. |Financial --> Payments --> Braintree Refunds| replace:: :menuselection:`Financial --> Payments --> Braintree Refunds`
   __ https://demo.tryton.org/model/account.payment.braintree.refund

.. _model-account.payment.journal:

Payment Journal
===============

When the *Account Payment Braintree Module* is activated, the *Payment Journal*
gains a property for the `Braintree Account
<model-account.payment.braintree.account>` for those journals where the
processing method is :guilabel:`Braintree`.

.. seealso::

   The `Payment Journal <account_payment:model-account.payment.journal>`
   concept is introduced by the :doc:`Account Payment Module
   <account_payment:index>`.

.. _model-account.payment.braintree.account:

Braintree Account
=================

The *Braintree Account* stores the credentials needed to communicate with the
Braintree API.

It also displays the URL to set up on Braintree for the webhooks_.

.. note::
   If no webhooks are set up, disputes will not update the `Payments
   <model-account.payment>`.

.. seealso::

   The Braintree Accounts can be found by opening the main menu item:

   |Financial --> Configuration --> Payments --> Braintree Accounts|__

   .. |Financial --> Configuration --> Payments --> Braintree Accounts| replace:: :menuselection:`Financial --> Configuration --> Payments --> Braintree Accounts`
   __ https://demo.tryton.org/model/account.payment.braintree.account

.. _webhooks: https://developers.braintreepayments.com/guides/webhooks/overview

.. _model-account.payment.braintree.customer:

Braintree Customer
==================

The *Braintree Customer* links a `Party <party:model-party.party>` to a
Braintree customer.

A `scheduled task <trytond:model-ir.cron>` runs every hour to create new
customers on Braintree and another to delete them if they have become inactive.

.. seealso::

   The Braintree Customers can be found by opening the main menu item:

   |Financial --> Payments --> Braintree Customers|__

   .. |Financial --> Payments --> Braintree Customers| replace:: :menuselection:`Financial --> Payments --> Braintree Customers`
   __ https://demo.tryton.org/model/account.payment.braintree.customer

.. _report-account.payment.braintree.checkout:

Braintree Checkout
==================

The *Braintree Checkout* report renders an :abbr:`HTML (Hypertext Markup
Language)` document using the Braintree Javascript library to display a
checkout form for `Payments <model-account.payment>` or `Braintree Customers
<model-account.payment.braintree.customer>`.
