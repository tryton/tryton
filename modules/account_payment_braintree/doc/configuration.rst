*************
Configuration
*************

The *Account Payment Braintree Module* uses values from settings in the
``[account_payment_braintree]`` section of the
:ref:`trytond:topics-configuration`.

.. _config-account_payment_braintree.payment_methods_cache:

``payment_methods_cache``
=========================

The ``payment_methods_cache`` defines the duration in seconds that `payment
methods`_ are kept in the :class:`~trytond:trytond.cache.Cache`.

The default value is: ``15 * 60``.

.. _payment methods: https://developers.braintreepayments.com/guides/payment-methods
