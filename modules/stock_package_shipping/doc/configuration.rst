*************
Configuration
*************

The *Stock Package Shipping Module* uses some settings from the
``[stock_package_shipping]`` section of the :doc:`configuration file
<trytond:topics/configuration>`.

.. _config-stock_package_shipping.filestore:

``filestore``
=============

This configuration value indicates whether the shipping label should be stored
in the :py:mod:`trytond:trytond.filestore` (``True``) or the database
(``False``).

The default value is: ``False``

.. _config-stock_package_shipping.store_prefix:

``store_prefix``
================

This is the prefix to use with the :py:mod:`trytond:trytond.filestore`.
This value is only used when the `filestore
<config-stock_package_shipping.filestore>` setting is in use.

The default value is: ``None``
