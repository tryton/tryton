******
Design
******

The *Account Stock Landed Cost Module* introduces and extends the following
concepts:

.. _model-account.landed_cost:

Landed Cost
===========

The *Landed Cost* defines how posted supplier `Invoice
<account_invoice:model-account.invoice>` lines with landed cost `Products
<concept-product>` are allocated to `Supplier Shipments
<stock:model-stock.shipment.in>`.

When a *Landed Cost* is posted, the :guilabel:`Unit Price` of each incoming
`Move <stock:model-stock.move>` from the supplier shipments is updated
according to the :guilabel:`Allocation Method`.
The default allocation method is :guilabel:`By Value` which allocates the cost
according to the value of each incoming move calculated as the
:guilabel:`Quantity` times the :guilabel:`Unit Price`.

.. note::
   The updated incoming moves can be filtered by `Categories
   <product:model-product.category>` or by `Products
   <product:model-product.product>`.

.. seealso::

   The Landed Costs can be found by opening the main menu item:

   |Financial --> Invoices --> Landed Costs|__

   .. |Financial --> Invoices --> Landed Costs| replace:: :menuselection:`Financial --> Invoices --> Landed Costs`
   __ https://demo.tryton.org/model/account.landed_cost

Wizards
-------

.. _wizard-account.landed_cost.post:

Post
^^^^

The *Post* wizard first shows how the costs will be allocated before posting
the *Landed Cost*.

.. _wizard-account.landed_cost.show:

Show
^^^^

The *Show* wizard displays the allocation that was applied by a posted *Landed
Cost*.

.. _model-account.configuration:

Account Configuration
=====================

When the *Account Stock Landed Cost Module* is activated, a `Sequence
<trytond:model-ir.sequence>` is set up in the *Account Configuration* to number
the `Landed Costs <model-account.landed_cost>`.

.. seealso::

   The `Account Configuration <account:model-account.configuration>` concept is
   introduced by the :doc:`Account Module <account:index>`.

.. _concept-product:

Product
=======

When the *Account Stock Landed Cost Module* is activated, *Products* gain an
additional property that is used to mark which services are a landed cost.

.. seealso::

   The `Product <product:concept-product>` concept is introduced by the
   :doc:`Product Module <product:index>`.
