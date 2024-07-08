*************
Configuration
*************

The *Account Export Module* uses some settings from the ``[account_export]``
section of the :ref:`trytond:topics-configuration`.

.. _config-account_export.filestore:

``filestore``
=============

This configuration value indicates whether the export files should be stored in
the :py:mod:`trytond:trytond.filestore` (``True``) or the database (``False``).

The default value is: ``False``

.. _config-account_export.store_prefix:

``store_prefix``
================

This is the prefix to use with the :py:mod:`trytond:trytond.filestore`.
This value is only used when the
`filestore <config-account_export.filestore>` setting is in use.

The default value is: ``None``
