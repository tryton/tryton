******
Design
******

The *Account Stock Continental Module* extends the following concepts:

.. _model-stock.move:

Stock Move
==========

When the :guilabel:`Account Stock Method` is set for the current `Fiscal Year
<model-account.fiscalyear>`, an `Account Move <account:model-account.move>` is
created for each *Stock Move* done with one `Location
<stock:model-stock.location>` of type :guilabel:`Storage` and the other of type
:guilabel:`Supplier`, :guilabel:`Customer`, :guilabel:`Production` or
:guilabel:`Lost and Found`.

When the stock enters the `Warehouse <stock:concept-stock.location.warehouse>`
the :guilabel:`Account Stock` is debited and the :guilabel:`Account Stock IN`
is credited with the value of the *Stock Move*.
The value is calculated from the :guilabel:`Unit Price` of the *Stock Move* or
the :guilabel:`Cost Price` of the `Product <product:model-product.product>` if
the cost method is :guilabel:`Fixed`.
When the stock leaves the warehouse, the :guilabel:`Account Stock` is credited
and the :guilabel:`Account Stock OUT` is debited.

.. _model-product.category:

Product Category
================

When the *Account Stock Continental Module* is activated, the *Product
Categories* marked as accounting categories gain new properties for the
`Accounts <account:model-account.account>` to use for the stock valuation.

.. seealso::

   The accounting `Product Category <account_product:model-product.category>`
   concept is introduced by the :doc:`Account Product Module
   <account_product:index>`.

.. _model-account.configuration:

Account Configuration
=====================

When the *Account Stock Continental Module* is activated, the *Account
Configuration* gains a new property for the `Journal
<account:model-account.journal>` to use for stock `Account Moves
<account:model-account.move>`.

.. seealso::

   The `Account Configuration <account:model-account.configuration>` concept is
   introduced by the :doc:`Account Module <account:index>`.

.. _model-account.fiscalyear:

Fiscal Year
===========

The *Account Stock Continental Module* adds a new property to the *Fiscal Year*
which defines the :guilabel:`Account Stock Method` to follow during that year.

.. seealso::

   The `Fiscal Year <account:model-account.fiscalyear>` concept is introduced
   by the :doc:`Account Module <account:index>`.
