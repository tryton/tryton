******
Design
******

The *Purchase Price List Module* extends the following concepts:

.. _model-party.party:

Party
=====

When the *Purchase Price List Module* is activated, :doc:`Price List
<product_price_list:index>` can also be defined for use with purchases from the
party.

.. seealso::

   The `Party <party:model-party.party>` concept is introduced by the module
   :doc:`Party Module <party:index>`.

.. _model-purchase.purchase:

Purchase
========

When the *Purchase Price List Module* is activated, the unit price of a product
is calculated using the :doc:`Price List <product_price_list:index>` if one is
defined for the supplier and if the `Product <product:concept-product>` does
not have a `Product Supplier Price <purchase:model-purchase.product_supplier>`.


.. seealso::

   The `Purchase <purchase:model-purchase.purchase>` concept is introduced by
   the module :doc:`Purchase Module <purchase:index>`.
