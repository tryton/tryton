Account Payment Stripe Module
#############################

The account_payment_stripe module allows to receive payment from `Stripe`_.
It uses `Stripe.js and Stripe Elements`_ in a checkout form to handle `Setup
Intent`_ and `Payment Intent`_ by card.

.. _`Stripe`: https://stripe.com/
.. _`Stripe.js and Stripe Elements`: https://stripe.com/docs/payments/elements
.. _`Setup Intent`: https://stripe.com/docs/api/setup_intents
.. _`Payment Intent`: https://stripe.com/docs/api/payment_intents

Account
*******

The Account stores the information about the Stripe account like the secret
key, the publishable key and the webhook signing secret.

The account's webhook endpoint is the URL used by stripe webhooks_. For
additional security, the Stripe's requests signature can be verified if the
webhook `signing secret`_ is set on the Account.
If no webhook is setup, a cron task fetches the new events.

.. _webhooks: https://stripe.com/docs/webhooks
.. _`signing secret`: https://stripe.com/docs/webhooks/signatures

Customer
********

The Customer allow to register parties as Stripe customers.
The checkout button opens the Stripe checkout form.

A cron task runs every hour to create new customers on Stripe and another to
delete them if they are inactivated.

Journal
*******

The journal has a new field for the Stripe account.

Payment
*******

The payment has also a checkout button which opens the Stripe checkout form.
A payment can be processed off-session using a source_ or `payment method`_
from the customer.
In case the payment method requires authorization, an email is sent to the
party with a link to the checkout form.
In case of error, it has also new fields which display the error messages.

A cron task runs every 15 minutes to charge each processing payment.

The capture box can be unchecked to only authorize on processing and capture
the amount in a second step.

If the payment is disputed, it will be updated at the closure of the dispute.

It is possible to partially or completely refund a payment.

.. _source: https://stripe.com/docs/sources
.. _`payment method`: https://stripe.com/docs/payments/payment-methods

Configuration
*************

The account_payment_stripe module uses the section ``account_payment_stripe``
to retrieve some parameters:

- ``sources_cache``: defines the duration in seconds the sources are kept in
  the cache. The default value is ``15 * 60``.

- ``max_network_retries``: defines the maximum number of retries the Stripe
  library may perform. The default value is ``3``.
