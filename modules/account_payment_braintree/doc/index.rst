Account Payment Braintree Module
################################

The account_payment_braintree module allows receipt of payments using
`Braintree`_.
It uses the `Drop-in UI`_ in a checkout form to handle the `payment method
nonce`_ for card and other supported payment methods.

.. _`Braintree`: https://www.braintreepayments.com/
.. _`Drop-in UI`: https://developers.braintreepayments.com/guides/drop-in/overview/javascript/v3
.. _`payment method nonce`: https://developers.braintreepayments.com/guides/payment-method-nonces

Account
*******

The Account stores the information about the Braintree account like the
merchant ID, the public and secret keys etc.

The account's webhook endpoint is the URL used by Braintree's webhooks_.
If no webhook is setup, disputes will not update existing payments.

.. _webhooks: https://developers.braintreepayments.com/guides/webhooks/overview

Customer
********

The Customer allows parties to be registered as Braintree customers.
The checkout/add card button opens the Braintree Drop-in UI form.

A scheduled task runs every hour to create new customers on Braintree and
another to delete them if they have become inactive.

Journal
*******

The journal has a new field to store the Braintree account if the process
method is set to "Braintree".

Payment
*******

The payment also has a checkout button which opens the Braintree Drop-in UI
form.
A payment can be processed using a nonce or a `payment method`_ from the
customer.
In case of an error, a new field displays the error message from Braintree.
The settle field can be unchecked to only authorize on processing and settle
the amount in a second step.

Two scheduled tasks run every 15 minutes to transact and settle each processing
payment.
Another scheduled task also runs every 15 minutes to pull updates for each
processing payment until they have succeeded or failed.

The Braintree payments have a pull button which can be used to force an update
with the braintree transaction.

.. _payment method: https://developers.braintreepayments.com/guides/payment-methods

Configuration
*************

The account_payment_braintree module uses the section
`account_payment_braintree` to retrieve some parameters:

- `payment_methods_cache`: defines the duration in seconds that payment methods
  are kept in the cache. The default value is `15 * 60`.
