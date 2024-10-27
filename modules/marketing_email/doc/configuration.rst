*************
Configuration
*************

The *Marketing Email Module* uses values from settings in the ``[marketing]``
section of the :ref:`trytond:topics-configuration`.

.. _config-marketing.email_from:

``email_from``
==============

The ``email_from`` defines the default address from which emails are sent.

The default value is: :ref:`trytond:config-email.from`.

.. _config-marketing.email_subscribe_url:

``email_subscribe_url``
=======================

The ``email_subscribe_url`` defines the URL to confirm the subscription.
The parameter ``token`` is added to it.

.. _config-marketing.email_unsubscribe_url:

``email_unsubscribe_url``
=========================

The ``email_unsubscribe_url`` defines the URL to unsubscribe an address.
The parameter ``token`` is added to it.

.. _config-marketing.email_spy_pixel:

``email_spy_pixel``
===================

If ``email_spy_pixel`` is set, a spy pixel is added to emails to detect and
report when the recipient opens it.

The default value is: ``False``
