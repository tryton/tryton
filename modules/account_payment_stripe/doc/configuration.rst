*************
Configuration
*************

The *Account Payment Stripe Module* uses values from settings in the
``[account_payment_stripe]`` section of the
:ref:`trytond:topics-configuration`.

.. note::

   To send emails, the general :ref:`trytond:config-email.from` section must
   also be configured.

.. _config-account_payment_stripe.sources_cache:

``sources_cache``
=================

The ``sources_cache`` defines the duration in seconds that the sources_ of a
`Stripe Customer <model-account.payment.stripe.customer>` are kept in the
:class:`~trytond:trytond.cache.Cache`.

The default value is: ``15 * 60``.

``payment_methods``
===================

The ``payment_methods`` defines the duration in seconds that the `payment
methods`_ for a `Stripe Customer <model-account.payment.stripe.customer>` are
kept in the :class:`~trytond:trytond.cache.Cache`.

The default value is: ``15 * 60``.

``max_network_retries``
=======================

The ``max_network_retries`` defines the maximum number of retries the `Stripe
library`_ may perform.

The default value is: ``3``.

.. _sources: https://docs.stripe.com/sources
.. _payment methods: https://docs.stripe.com/payments/payment-methods
.. _Stripe library: https://pypi.org/project/stripe/
