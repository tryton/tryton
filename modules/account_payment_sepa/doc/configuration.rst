*************
Configuration
*************

The *Account Payment SEPA Module* uses values from settings in the
``[account_payment_sepa]`` section of the :ref:`trytond:topics-configuration`.

.. _config-account_payment_sepa.filestore:

``filestore``
=============

If ``filestore`` is set, the SEPA messages are stored in the
:class:`~trytond:trytond.filestore.FileStore`.

The default value is: ``False``

.. _config-account_payment_sepa.store_prefix:

``store_prefix``
================

The ``store_prefix`` is the prefix to use for the
:class:`~trytond:trytond.filestore.FileStore`.

The default value is: ``None``
