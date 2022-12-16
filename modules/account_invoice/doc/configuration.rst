*************
Configuration
*************

The *Account Invoice Module* uses some settings from the ``[account_invoice]``
section of the :doc:`configuration file <trytond:topics/configuration>`.

.. _config-account_invoice.filestore:

``filestore``
=============

This configuration value indicates whether the cached copy of the
`Customer Invoice Reports <report-account.invoice>` should be stored in the
:py:mod:`trytond:trytond.filestore` (``True``) or the database (``False``).

The default value is: ``False``

.. _config-account_invoice.store_prefix:

``store_prefix``
================

This is the prefix to use with the :py:mod:`trytond:trytond.filestore`.
This value is only used when the
`filestore <config-account_invoice.filestore>` setting is in use.

The default value is: ``None``
