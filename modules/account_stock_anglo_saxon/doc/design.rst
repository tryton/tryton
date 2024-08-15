******
Design
******

The *Account Stock Anglo-Saxon Module* extends the following concepts:

.. _model-product.category:

Product Category
================

When *Account Stock Anglo-Saxon Module* is activated, the *Product Categories*
marked as accounting categories gain a new property for the :abbr:`COGS (Cost
Of Goods Sold)` `Account <account:model-account.account>`.

.. seealso::

   The accounting `Product Category <account_product:model-product.category>`
   concept is introduced by the :doc:`Account Product Module
   <account_product:index>`.

.. _model-account.fiscalyear:

Fiscal Year
===========

The *Account Stock Anglo-Saxon Module* adds a new :guilabel:`Anglo-Saxon`
option to the *Fiscal Year's* :guilabel:`Account Stock Method`.

.. seealso::

   The Account Stock Method for the `Fiscal Year
   <account_stock_continental:model-account.fiscalyear>` is introduced by the
   :doc:`Account Stock Continental Module <account_stock_continental:index>`.

.. _model-account.invoice:

Invoice
=======

When the :guilabel:`Account Stock Method` is set to :guilabel:`Anglo-Saxon` for
the *Invoice's* `Fiscal Year <model-account.fiscalyear>`, its `Move
<account:model-account.move>` is setup as follows.

For supplier invoices, the cost of the `Product
<account_product:concept-product>`, when it was received, is debited to the
:guilabel:`Account Stock IN` and any difference between that and the amount on
the invoice is debited to the :guilabel:`Account Expense`.
If the product has not been received yet, the amount from the invoice is used
as the cost.
The reverse operation is performed for supplier credit notes.

For customer invoices, the cost of the *Product* at the time of delivery is
credited to the :guilabel:`Account Stock OUT` and is debited to the
:guilabel:`Account Cost of Goods Sold`.
If the delivery has not yet taken place, the current cost is used.
The reverse operation is performed for customer credit notes.

.. seealso::

   The `Invoice <account_invoice:model-account.invoice>` concept is introduced
   by the :doc:`Account Invoice Module <account_invoice:index>`.
