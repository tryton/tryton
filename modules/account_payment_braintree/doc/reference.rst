*************
API Reference
*************

.. _Braintree Checkout:

Braintree Checkout
==================

The *Account Payment Braintree Module* defines a route to checkout a `Payment
<model-account.payment>` or a `Braintree Customer
<model-account.payment.braintree.customer>`:

   - ``GET`` ``/<database_name>/account_payment_braintree/checkout/<model>/<id>``:
     Returns an :abbr:`HTML (Hypertext Markup Language)` page using the `Checkout
     <report-account.payment.braintree.checkout>` report.

      ``model`` the name of the model: ``account.payment`` or
      ``account.payment.braintree.customer``.
      ``id`` the :attr:`~trytond:trytond.model.Model.id` of the record.

   - ``POST`` ``/<database_name>/account_payment_braintree/checkout/<model>/<id>``:
     Retrieves the form with ``payment_method_nonce`` (and optionally
     ``device_data``) to set on the record.

.. _Braintree Webhook:

Braintree Webhook
=================

The *Account Payment Braintree Module* defines a route to receive the Braintree's webhooks_:

   - ``POST`` ``/<database_name>/account_payment_braintree/webhook/<account>``:

      ``account`` is the webhook identifier of the `Account
      <model-account.payment.braintree.account>`.

.. _webhooks: https://developers.braintreepayments.com/guides/webhooks/overview
