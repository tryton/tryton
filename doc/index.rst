Account Payment Stripe Module
#############################

The account_payment_stripe module allows to receive payment from `Stripe`_.
It uses the checkout form in the browser.

.. _`Stripe`: https://stripe.com/

Account
*******

The Account stores the information about the Stripe account like the secret key
and the publishable key.

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
