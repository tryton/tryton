******
Design
******

The *Sale Invoice Date Module* introduces some new concepts and extends
existing concepts.

.. _model-sale.invoice.term:

Invoice Term
============

The *Invoice Term* stores the method used to calculate the date of the invoice
based on the moment the invoice is created.

.. seealso::

   Invoice terms are created and managed from the main menu item:

      |Sales --> Configuration --> Invoice Terms|__

      .. |Sales --> Configuration --> Invoice Terms| replace:: :menuselection:`Sales --> Configuration --> Invoice Terms`
      __ https://demo.tryton.org/model/sale.invoice.term

.. _model-sale.sale:

Sale
====

The *Sale* concept is extended to store the `Invoice Term
<model-sale.invoice.term>` from the `Party <party:model-party.party>` or the
`Configuration <sale:model-sale.configuration>`.

.. seealso::

   The `Sale <sale:model-sale.sale>` concept is introduced by the :doc:`Sale
   Module <sale:index>`.
