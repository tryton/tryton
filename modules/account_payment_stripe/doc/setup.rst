*****
Setup
*****

.. _Configure Stripe credentials:

Configure Stripe credentials
============================

First you must `register with Stripe <https://dashboard.stripe.com/register>`_
and get your `API keys <https://dashboard.stripe.com/apikeys>`_.

Then create a `Stripe Account <model-account.payment.stripe.account>` and copy
the :guilabel:`Secret Key` and :guilabel:`Publishable Key`.

You can also set up a webhook endpoint by clicking on the :guilabel:`New URL`
button.
Then on Stripe add an `endpoint <https://dashboard.stripe.com/webhooks>`_ by
copying the new URL and selecting the events you want to receive.
For more security, you can reveal the :guilabel:`Signing secret` and copy it to
the Stripe account.
