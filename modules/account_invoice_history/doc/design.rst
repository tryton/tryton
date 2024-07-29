******
Design
******

The *Account Invoice History Module* extends the following concepts:

.. _model-account.invoice:

Invoice
=======

When the *Account Invoice History Module* is activated, the related fields
(i.e. :guilabel:`Party`, :guilabel:`Tax Indentifier`, :guilabel:`Invoice
Address` and :guilabel:`Payment Term`) of the *Invoice* have their
:attr:`~trytond.model.fields.Many2One.datetime_field` attribute set to when the
invoice was numbered.

.. seealso::

   The `Invoice <account_invoice:model-account.invoice>` concept is introduced
   by the :doc:`Account Invoice Module <account_invoice:index>`.
