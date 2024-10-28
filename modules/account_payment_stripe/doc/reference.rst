*************
API Reference
*************

.. _Stripe Checkout:

Stripe Checkout
===============

The *Account Payment Stripe Module* defines a route to checkout a `Payment
<model-account.payment>` or a `Stripe Customer
<model-account.payment.stripe.customer>`:

   - ``GET`` ``/<database_name>/account_payment_stripe/checkout/<model>/<id>``:
     Returns an :abbr:`HTML (Hypertext Markup Language)` page using the
     `Checkout <report-account.payment.stripe.checkout>` report.

      ``model`` the name of the module: ``account.payment`` or
      ``account.payment.stripe.customer``.
      ``id`` the :attr:`~trytond:trytond.model.Model.id` of the record.

   - ``POST`` ``/<database_name>/account_payment_stripe/checkout/<model>/<id>``:
     Updates the `setup intent`_ of the record.

.. _setup intent: https://docs.stripe.com/payments/setup-intents

.. _Stripe Webhook:

Stripe Webhook
==============

The *Account Payment Stripe Module* defines a route to receive the Stripe's
webhooks_:

   - ``POST`` ``/<database_name>/account_payment_stripe/webhook/<account>``:

      ``account`` is the webhook identifier of the `Account
      <model-account.payment.stripe.account>`.

.. _webhooks: https://docs.stripe.com/webhooks
