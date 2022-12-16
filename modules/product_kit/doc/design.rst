******
Design
******

The *Product Kit Module* module introduces the following concepts:

.. _concept-product:

Product
=======

When the *Product Kit Module* is activated, products gain some extra properties.
These include a new type "Kit" which corresponds to a product composed of other
goods defined by a list of `Components <model-product.component>`.

.. seealso::

   The `Product <product:concept-product>` concept is introduced by the
   :doc:`Product Module <product:index>`.

.. _model-product.component:

Product Component
=================

The *Product Component* concept defines the quantity of a product that is part
of another product.

.. _model-sale.sale:

Sale
====

When the *Product Kit Module* is activated, components are added to sales when
the sale is quoted.

For `Sale Lines <model-sale.line>` with a kit `Product <concept-product>`, a
`Sale Line Component <model-sale.line.component>` is created for each `Product
Component <model-product.component>`.
These components are used as the origins for the `Stock Moves
<stock:model-stock.move>` and the sale lines of the `Invoice Lines
<account_invoice:model-account.invoice.line>`.
When the `Invoice <account_invoice:model-account.invoice>` method is on
shipment, the smallest ratio of shipped components is used to calculate the
quantity invoiced.

For `Sale Lines <model-sale.line>` with a non-kit product containing `Product
Components <model-product.component>`, a sale line is created for each one.

When the sale is reset to draft, all created components are deleted.

.. _model-sale.line:

Line
----

The sale lines gain a list of `Sale Line Components
<model-sale.line.component>` and a list of children which are created when the
`Sale <sale:model-sale.sale>` is quoted.

.. _model-sale.line.component:

Line Component
--------------

The *Sale Line Component* concept defines for a `Sale Line
<sale:model-sale.line>` the quantity of a `Product Component
<model-product.component>` to be shipped instead of the kit.

.. seealso::

   The `Sale <sale:model-sale.sale>` model is introduced by the :doc:`Sale
   Module <sale:index>`.


.. _model-purchase.purchase:

Purchase
========

When the *Product Kit Module* is activated, components are added to `Purchases
<purchase:model-purchase.purchase>` when the purchase is quoted.

For `Purchase Lines <model-purchase.line>` with a kit `Product
<concept-product>`, a `Purchase Line Component <model-sale.line.component>` is
created for each `Product Component <model-product.component>`.
These components are used as the origins for the `Stock Moves
<stock:model-stock.move>` and the purchase lines of the `Invoice Lines
<account_invoice:model-account.invoice.line>`.
When the `Invoice <account_invoice:model-account.invoice>` method is on
shipment, the smallest ratio of received components is used to calculate the
quantity invoiced.

For `Purchase Lines <model-purchase.line>` with a non-kit product containing
`Product Components <model-product.component>`, a purchase line is created for
each one.

When the purchase is reset to draft, all created components are deleted.

.. _model-purchase.line:

Line
----

The purchase lines gain a list of `Purchase Line Components
<model-purchase.line.component>` and a list of children which are created when
the `Purchase <purchase:model-purchase.purchase>` is quoted.

.. _model-purchase.line.component:

Line Component
--------------

The *Purchase Line Component* concept defines for a `Purchase Line
<purchase:model-purchase.line>` the quantity of a `Product Component
<model-product.component>` to be received instead of the kit.

.. seealso::

   The `Purchase <purchase:model-purchase.purchase>` model is introduced by the
   :doc:`Purchase Module <purchase:index>`.
