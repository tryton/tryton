******
Design
******

The *Customs Modules* introduces or extends the following concepts:

.. _model-customs.tariff.code:

Tariff Code
===========

The *Tariff Code* stores the `Harmonized System`_ code for a `Country
<country:model-country.country>` or `Organization
<country:model-country.organization>` active for a period of the year.

.. seealso::

   The *Tariff Codes* can be found by opening the main menu item:

   |Products --> Customs --> Tariff Codes|__

   .. |Products --> Customs --> Tariff Codes| replace:: :menuselection:`Products --> Customs --> Tariff Codes`
   __ https://demo.tryton.org/model/customs.tariff.code

.. _model-customs.duty.rate:

Duty Rate
=========

The *Duty Rate* stores the import or export rate applied for a `Tariff Code
<model-customs.tariff.code>` over a period and a `Country
<country:model-country.country>` or `Organization
<country:model-country.organization>`.
The rate can be expressed as a fixed amount or an amount per `Unit of Measure
<product:model-product.uom>` in a `Currency
<currency:model-currency.currency>`.

.. seealso::

   The *Duty Rates* can be found by opening the main menu item:

   |Products --> Customs --> Duty Rates|__

   .. |Products --> Customs --> Duty Rates| replace:: :menuselection:`Products --> Customs --> Duty Rates`
   __ https://demo.tryton.org/model/customs.duty.rate

.. _concept-product:

Product
=======

The *Product* concept is extended with a set of methods that allow retrieving
the product's `Tariff codes <model-customs.tariff.code>` based on criteria.

The tariff codes can be set directly on the product or on a special type of
`Product Category <model-product.category>`.
Unlike standard product categories, each product can only have a single customs
category.

.. seealso::

   The `Product <product:concept-product>` concept is introduced by the
   :doc:`Product Module <product:index>`.

.. _model-product.category:

Product Category
================

The *Customs Module* allows some *Product Categories* to be marked as customs
categories.
These product categories can have customs properties such as `Tariff Codes
<model-customs.tariff.code>` associated with them.

When placing categories into a structure all the categories in the structure
must be either standard categories or customs categories.
This means a customs category cannot have a standard category as its parent or
as any of its subcategories.

.. seealso::

   The `Product Category <product:model-product.category>` concept is
   introduced by the :doc:`Product Module <product:index>`.

.. _`Harmonized System`: http://en.wikipedia.org/wiki/Harmonized_System
