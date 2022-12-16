******
Design
******

The *Product Module* introduces the following concepts:

.. _concept-product:

Product
=======

The *Product* is the main concept introduced by the *Product Module*.
It represents an item or service that Tryton stores information about, and is
often something that gets bought, sold, or produced.

In Tryton product definitions are made up from two parts, the
`Product Template <model-product.template>` and the
`Product Variant <model-product.product>`.
Both of these are sometimes referred to as the *Product*, depending on the
context.

Each product template can have many different product variants, but each
product variant is based exclusively on one product template.

A product's full code is made up from a prefix code which is defined on the
product template and a suffix code which is specified on the product variant.
The full product code can then be used as the product's |SKU|_.

.. |SKU| replace:: :abbr:`SKU (Stock Keeping Unit)`
.. _SKU: https://en.wikipedia.org/wiki/Stock_keeping_unit

.. _model-product.template:

Product Template
----------------

The *Product Template* defines the set of properties common to a group of
`Product Variants <model-product.product>`.
These properties include things like its list price, its type, its code, what
`Categories <model-product.category>` it is in, and what
`Units of Measure <model-product.uom>` are used by default for quantities of
the product.

.. seealso::

   A list of product templates can be found by opening the main menu item:

      |Products --> Products|__

      .. |Products --> Products| replace:: :menuselection:`Products --> Products`
      __ https://demo.tryton.org/model/product.template

.. _model-product.product:

Product Variant
---------------

Each *Product Variant* inherits many of its properties from its
`Product Template <model-product.template>`.
It does, however, have some properties that are specific to each variant
such as the description, cost price, and suffix code which is important to
distinguish between different variants.

The identifiers that are used to refer to a product are also specific to a
product variant.
A product identifier is made up from a type and a code.

Some of the supported types of identifier include:

* International Article Number (EAN)
* International Standard Audiovisual Number (ISAN)
* International Standard Book Number (ISBN)
* International Standard Identifier for Libraries (ISIL)
* International Securities Identification Number (ISIN)
* International Standard Music Number (ISMN)

.. seealso::

   A list of all the product variants is available from the main menu item:

      |Products --> Products --> Variants|__

      .. |Products --> Products --> Variants| replace:: :menuselection:`Products --> Products --> Variants`
      __ https://demo.tryton.org/model/product.product

.. _model-product.category:

Category
========

The product *Category* concept provides a flexible way of grouping
`Product Templates <model-product.template>` together.
The categories can be structured by giving them a parent category and some
sub-categories.

.. seealso::

   A list of product categories can be found by opening the main menu item:

      |Products --> Categories|__

      .. |Products --> Categories| replace:: :menuselection:`Products --> Categories`
      __ https://demo.tryton.org/model/product.category

.. _model-product.uom:

Unit of Measure
===============

The *Unit of Measure* concept provides the units by which the quantity of a
`Product <concept-product>` is measured.
These are things like, meter, mile, kilogram, hour, gallon, and so on.

Each unit of measure belongs to a
`Unit of Measure Category <model-product.uom.category>`.

Quantities can be converted to a different unit of measure from the same
category using the unit of measures' rates or factors.
It is also possible to specify the rounding precision and number of decimal
digits used when rounding or displaying values from the unit of measure.

.. seealso::

   The units of measure can be found using the main menu item:

      |Products --> Units of Measure|__

      .. |Products --> Units of Measure| replace:: :menuselection:`Products --> Units of Measure`
      __ https://demo.tryton.org/model/product.uom

.. _model-product.uom.category:

Unit of Measure Category
========================

A *Unit of Measure Category* is used to group together
`Units of Measure <model-product.uom>` that are used to measure the same type
of property.
These are things like length, weight, time or volume.

.. seealso::

   The units of measure can be found using the main menu item:

      |Products --> Units of Measure --> Categories|__

      .. |Products --> Units of Measure --> Categories| replace:: :menuselection:`Products --> Units of Measure --> Categories`
      __ https://demo.tryton.org/model/product.uom.category

.. _model-product.configuration:

Configuration
=============

The product *Configuration* contains the settings which are used to configure
the behaviour and default values for things associated with products.

There are configuration options for the sequences to use to automatically
generate codes for `Products <concept-product>`.

.. seealso::

   The product configuration can be found using the main menu item:

      |Products --> Configuration --> Configuration|__

      .. |Products --> Configuration --> Configuration| replace:: :menuselection:`Products --> Configuration --> Configuration`
      __ https://demo.tryton.org/model/product.configuration/1
