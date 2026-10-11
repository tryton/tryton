******
Design
******

The *Sale Credit Limit Module* extends the following concepts:

.. _model-party.party:

Party
=====

When the *Sale Credit Limit Module* is activated, the party's :guilabel:`Credit
Amount` also includes the uninvoiced amount of `Sales <sale:model-sale.sale>`
that have been confirmed or are being processed.
This increases the credit exposure calculated by the :doc:`Account Credit Limit
Module <account_credit_limit:index>`.

.. seealso::

   The `Party <party:model-party.party>` concept is introduced by the
   :doc:`Party Module <party:index>`.

.. _model-sale.sale:

Sale
====

When the *Sale Credit Limit Module* is activated, confirming a sale will check
the `party <model-party.party>`'s credit limit before the sale can be confirmed
if the shipment method is :guilabel:`On Order`.
The amount tested is the untaxed sale amount.

.. seealso::

   The `Sale <sale:model-sale.sale>` concept is introduced by the
   :doc:`Sale Module <sale:index>`.
