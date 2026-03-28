******
Design
******

The *Account Stock EU Excise Module* introduces and extends the following
concepts:

.. _model-account.stock.eu.excise.tax:

Excise Tax
==========

The excise tax defines the rates and the `unit <product:model-product.uom>` to
calculate the duties per `country <country:model-country.country>`.

.. seealso::

   The excise taxes can be found by opening the main menu item:

      |Financial --> Configuration --> Taxes --> Excise Taxes|__

      .. |Financial --> Configuration --> Taxes --> Excise Taxes| replace:: :menuselection:`Financial --> Configuration --> Taxes --> Excise Taxes`
      __ https://demo.tryton.org/model/account.stock.eu.excise.tax

.. _model-account.stock.eu.excise.declaration:

Excise Declaration
==================

The *Excise Declaration* shows the quantities of input and output per `Excise
Tax <model-account.stock.eu.excise.tax>` for a `Warehouse
<stock:concept-stock.location.warehouse>` over a period.

.. seealso::

   The excise declarations can be opened using the main menu item:

      |Financial --> Reporting --> Excise Declarations|__

      .. |Financial --> Reporting --> Excise Declarations| replace:: :menuselection:`Financial --> Reporting --> Excise Declarations`
      __ https://demo.tryton.org/model/account.stock.eu.excise.declaration

.. _model-account.stock.eu.excise.declaration.product:

Excise Declaration Product
==========================

The *Excise Declaration Product* shows the same quantities as the `Excise
Declaration <model-account.stock.eu.excise.declaration>` but per `Product
<product:model-product.product>`.

.. seealso::

   The excise declaration products can be opened using the main menu item:

      |Financial --> Reporting --> Excise Declaration Products|__

      .. |Financial --> Reporting --> Excise Declaration Products| replace:: :menuselection:`Financial --> Reporting --> Excise Declaration Products`
      __ https://demo.tryton.org/model/account.stock.eu.excise.declaration.product

.. _model-account.stock.eu.excise.declaration.product.line:

Excise Declaration Product Lines
================================

The *Excise Declaration Product Lines* shows the `stock moves
<stock:model-stock.move>` used to calculate the quantities for the related
`Excise Declaration Product
<model-account.stock.eu.excise.declaration.product>`.

.. seealso::

   The excise declaration product lines can be opened from the link on the
   `Excise Declaration Product
   <model-account.stock.eu.excise.declaration.product>`.

.. _model-party.identifier:

Party Identifier
================

The party identifier with an excise number type is extended to specify the
excise codes for which it is authorised.

.. seealso::

   The `Party Identifier <party:model-party.identifier>` concept is introduced
   by the :doc:`Party Module <party:index>`.

.. _concept-product:

Product
=======

When the *Account Stock EU Excise Module* is activated, the product gains new
properties to specifying the `Excise Code <model-product.eu.excise_code>` and
the `Excise Taxes <model-account.stock.eu.excise.tax>` applicable to
the goods per `country <country:model-country.country>`.

.. seealso::

   The `Product <product:concept-product>` concept is introduced by the
   :doc:`Product Module <product:index>`.

.. _model-product.eu.excise_code:

Excise Code
===========

The excise code stores the codes from the `System for Exchange of Excise Data
<https://data.europa.eu/data/datasets/seed-system-for-exchange-of-excise-data>`_.

.. seealso::

   A list of excise codes can be found by opening the main menu item:

      |Products --> Configuration --> Excise Codes|__

      .. |Products --> Configuration --> Excise Codes| replace:: :menuselection:`Products --> Configuration --> Excise Codes`
      __ https://demo.tryton.org/model/product.eu.excise_code

.. _model-product.price_list:

Price List
==========

When the *Account Stock EU Excise Module* is activated, the price list gains
new criteria based on `Excise Tax <model-account.stock.eu.excise.tax>` and duty
suspension.

.. seealso::

   The Price List concept is introduced by the :doc:`Product Price List Module
   <product_price_list:index>`.

.. _concept-stock.location.warehouse:

Warehouse
=========

When the *Account Stock EU Excise Module* is activated, the warehouse gains a
property that stores the `Excise Numbers <model-party.identifier>` per `Company
<company:model-company.company>`.

.. seealso::

   The `Warehouse <stock:concept-stock.location.warehouse>` concept is
   introduced by the :doc:`Stock Module <stock:index>`.

.. _concept-stock.shipment:

Shipment
========

When the *Account Stock EU Excise Module* is activated, the shipments gain new
properties that stores information for the excise duties like the `Excise
Number <model-party.identifier>` of the other party.

.. seealso::

   The `Shipment <stock:concept-stock.shipment>` concept is introduced by the
   :doc:`Stock Module <stock:index>`.

.. _model-stock.move:

Stock Move
==========

When the *Account Stock EU Excise Module* is activated, the stock move stores
the type of excise duty that applies.

.. seealso::

   The `Stock Move <stock:model-stock.move>` concept is introduced by the
   :doc:`Stock Module <stock:index>`.

.. _model-sale.sale:

Sale
====

When the *Account Stock EU Excise Module* is activated, sales gain new
properties for storing the `Excise Number <model-party.identifier>` of the
customer and calculating the duty amount.

.. seealso::

   The `Sale <sale:model-sale.sale>` concept is introduced by the :doc:`Sale
   Module <sale:index>`.
