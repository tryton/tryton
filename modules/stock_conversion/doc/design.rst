******
Design
******

The *Stock Conversion Module* introduces or extends the following concepts.

.. _model-stock.conversion.rule:

Conversion Rule
===============

A conversion rule specifies the process by which one `Product
<product:concept-product>` can be converted into another.


.. _model-stock.conversion:

Conversion
==========

A *Conversion* is an order to instantly transform a specific quantity of a
`Product <product:concept-product>` in place into another product.
The resulting quantity is calculated using the corresponding `Rule
<model-stock.conversion.rule>`.

.. seealso::

   The conversions can be found using the main menu item:

      |Inventory & Stock --> Conversions|__

      .. |Inventory & Stock --> Conversions| replace:: :menuselection:`Inventory & Stock --> Conversions`
      __ https://demo.tryton.org/model/stock.conversion

.. _model-stock.configuration:

Configuration
=============

When the *Stock Conversion Module* is activated, the configuration gains a
property to store the sequence used to number the `Conversions
<model-stock.conversion>`.

.. seealso::

   The `Configuration <stock:model-stock.configuration>` concept is
   introduced by the :doc:`Stock Module <stock:index>`.

.. _model-stock.location:

Location
========

When the *Stock Conversion Module* is activated, warehouses gain an extra
location property for :guilabel:`Conversion` which is used as the default value
when converting products.

.. seealso::

   The `Location <stock:model-stock.location>` concept is introduced by the
   :doc:`Stock Module <stock:index>`.

.. _model-product.product:

Product
=======

When the *Stock Conversion Module* is activated, products gain an additional
property in the form of a list of `Conversion Rules
<model-stock.conversion.rule>` which defines the products to which they can be
converted.

.. seealso::

   The `Product <product:model-product.product>` concept is introduced by the
   :doc:`Product Module <product:index>`.
