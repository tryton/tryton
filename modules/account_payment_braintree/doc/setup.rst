*****
Setup
*****

.. _Configure Braintree credentials:

Configure Braintree credentials
===============================

First you must `register with Braintree
<https://www.braintreegateway.com/login>`_ and get the `API credentials
<https://developer.paypal.com/braintree/articles/control-panel/important-gateway-credentials>`_.

Then create a `Braintree Account <model-account.payment.braintree.account>` and
set up the `environment
<https://developer.paypal.com/braintree/articles/get-started/try-it-out#sandbox-versus-production>`_
and copy the :guilabel:`Merchant ID`, :guilabel:`Public Key` and
:guilabel:`Private Key`.

You can also set up a webhook endpoint by clicking on the :guilabel:`New URL`
button.
Then, on Braintree, create a new `Webhook
<https://developer.paypal.com/braintree/articles/control-panel/webhooks>`_ by
copying the new URL and selecting the events you want to receive.
