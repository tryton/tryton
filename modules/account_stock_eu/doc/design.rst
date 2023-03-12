******
Design
******

The *Account Stock EU Module* introduces and extends the following concepts:

.. _model-account.stock.eu.intrastat.declaration:

Intrastat Declaration
=====================

A *Declaration* is created for each month and country from which the company
has exported to or imported goods from other European countries.
Each *Declaration* is closed once it has been exported to be filled to the
authorities.
If a change happens later, the *Declaration* is reopened.

.. seealso::

   Intrastat Declarations can be found by opening the main menu item:

      |Financial --> Processing --> Intrastat Declarations|__

      .. |Financial --> Processing --> Intrastat Declarations| replace:: :menuselection:`Financial --> Processing --> Intrastat Declarations`
      __ https://demo.tryton.org/model/account.stock.eu.intrastat.declaration

.. _wizard-account.stock.eu.intrastat.declaration.export:

Intrastat Declaration Export
============================

The *Intrastat Declaration Export* wizard generates a file the report for the
*Declaration*.
The supported countries are:

   * Belgium
   * Spain

If the country is not supported, a generic `CSV
<https://en.wikipedia.org/wiki/Comma-separated_values>`_ is used.

.. _model-account.stock.eu.intrastat.transaction:

Intrastat Transaction
=====================

It stores the nature of the transactions.


.. _model-account.stock.eu.intrastat.transport:

Intrastat Transport
===================

It stores the type of transports for the extended declaration.

.. _concept-stock.shipment:

Shipment
========

The *Shipment* concepts are extended to store or compute the origin country and
the destination country.

.. seealso::

   The `Shipment <stock:concept-stock.shipment>` concepts are introduced by the
   :doc:`Stock Module <stock:index>`.

.. _model-stock.move:

Stock Move
==========

The *Stock Move* concept is extended to store the needed information for
Intrastat declaration.

.. seealso::

   The `Stock Move <stock:model-stock.move>` concept is introduced by the
   :doc:`Stock Module <stock:index>`.

.. _model-customs.tariff.code:

Tariff Code
===========

The *Tariff Code* concept is extended to store an optional additional unit to
include on Intrastat declaration.

.. seealso::

   The Tariff Code concept is introduced by the :doc:`Customs Module
   <customs:index>`.

.. _model-account.fiscalyear:

Fiscal Year
===========

The *Fiscal Year* concept is extended to store if the company should use the
extended Intrastat declaration for the period.

.. seealso::

   The `Fiscal Year <account:model-account.fiscalyear>` concept is introduced
   by the :doc:`Account Module <account:index>`.

.. _model-country.subdivision:

Subdivision
===========

The *Subdivision* concept is extended to store the Intrastat code.

.. seealso::

   The `Subdivision <country:model-country.subdivision>` concept is introduced
   by the :doc:`Country Module <country:index>`.
