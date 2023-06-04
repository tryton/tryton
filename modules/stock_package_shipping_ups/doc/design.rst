******
Design
******

The *Stock Package Shipping UPS Module* introduces some new concepts.

.. _model-carrier:

Carrier
=======

When the *Stock Package Shipping UPS Module* is activated, carrier can be
configured to use the "UPS" shipping service.
When this configuration is chosen, carrier gains some extra properties like the
UPS service type, the label image format and notifications.

.. seealso::

   The Carrier model is introduced by the :doc:`Carrier Module
   <carrier:index>`.

.. _model-carrier.credential.ups:

UPS Credential
==============

A *UPS Credential* stores the credentials to communicate with the UPS APIs.

The first matching credential is used for carrier with "UPS" shipping service.

.. seealso::

   Credentials are found by opening the main menu item:

      |Carrier --> Configuration --> UPS Credentials|__

      .. |Carrier --> Configuration --> UPS Credentials| replace:: :menuselection:`Carrier --> Configuration --> UPS Credentials`
      __ https://demo.tryton.org/model/carrier.credential.ups

.. _model-stock.package.type:

Package Type
============

When the *Stock Package Shipping UPS Module* is activated, the UPS code can be
defined on the package type.

.. seealso::

   The Package Type model is introduced by the :doc:`Stock Package Module
   <stock_package:index>`.
