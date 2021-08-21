*************
Configuration
*************

The *Stock Package Shipping Sendcloud Module* uses values from settings in the
``[stock_package_shipping_sendcloud]`` section of the :doc:`configuration file
<trytond:topics/configuration>`.

.. _config-stock_package_shipping_sendcloud.addresses_cache:

``addresses_cache```
====================

The ``addresses_cache`` defines the duration in seconds the sender addresses
are kept in the cache.

The default value is: ``15 * 60``.

.. _config-stock_package_shipping_sendcloud.shipping_methods_cache:

```shipping_methods_cache```
============================

The ``shipping_methods_cache`` defines the duration in seconds the shipping
methods are kept in the cache.

The default value is: ``60 * 60``.
