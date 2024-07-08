*************
Configuration
*************

The *Account Statement Module* uses values from settings in the
``[account_statement]`` section of the :ref:`trytond:topics-configuration`.

.. _config-account_statement.filestore:

``filestore``
=============

This configuration value indicates whether the `Statement
<model-account.statement>` origin files should be stored in the
:py:mod:`trytond:trytond.filestore` (``True``) or the database (``False``).

The default value is: ``False``


``store_prefix``
================

This is the prefix to use with the :py:mod:`trytond:trytond.filestore`.
This value is only used when the `filestore
<config-account_statement.filestore>` setting is in use.

The default value is: ``None``
