*************
Configuration
*************

The *Stock Package Shipping UPS Module* uses values from the settings in the
``[stock_package_shipping_ups]`` section of the :doc:`configuration file
<trytond:topics/configuration>`.

.. _config-stock_package_shipping_ups.requests_timeout:

``requests_timeout``
====================

The ``requests_timeout`` defines the time in seconds to wait for the UPS APIs
answer before failing.

The default value is: ``300``
