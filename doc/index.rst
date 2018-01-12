Account Payment Stripe Module
#############################

The account_payment_stripe module allows to receive payment from `Stripe`_.
It uses the checkout form in the browser.

.. _`Stripe`: https://stripe.com/

Account
*******

The Account stores the information about the Stripe account like the secret
key, the publishable key and the webhook signing secret.

The account's webhook endpoint is the URL used by stripe webhooks_. For
additional security, the Stripe's requests signature can be verified if the
webhook `signing secret`_ is set on the Account.

.. _webhooks: https://stripe.com/docs/webhooks
.. _`endpoint secret`: https://stripe.com/docs/webhooks#signatures

Customer
********

The Customer allow to register parties as Stripe customers.
The checkout button opens in the browse the Stripe checkout form.

A cron task runs every hour to create new customers on Stripe and another to
delete them if they are inactivated.

Journal
*******

The journal has a new field for the Stripe account.

Payment
*******

The payment has also a checkout button which opens the Stripe checkout form.
In case of error, it has also new fields which display the error messages.

A cron task runs every 15 minutes to charge each processing payment.

The capture box can be unchecked to only authorize on processing and capture
the amount in a second step.

If the payment is disputed, it will be updated at the closure of the dispute.
