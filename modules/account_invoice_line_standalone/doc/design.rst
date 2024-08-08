******
Design
******

The *Account Invoice Line Standalone Module* extends the following concepts:

.. _model-account.invoice:

Invoice
=======

When the *Account Invoice Line Standalone Module* is activated, the invoice
lines gain buttons which :guilabel:`Add` and :guilabel:`Remove` standalone
lines on the invoice.

.. seealso::

   The `Invoice <account_invoice:model-account.invoice>` concept is introduced
   by the :doc:`Account Invoice Module <account_invoice:index>`.

.. seealso::

   The customer invoice lines can be seen by opening the main menu item:

      |Financial --> Invoices --> Customer Invoices --> Lines|__

      .. |Financial --> Invoices --> Customer Invoices --> Lines| replace:: :menuselection:`Financial --> Invoices --> Customer Invoices --> Lines`
      __ https://demo.tryton.org/model/account.invoice.line;domain=[["invoice_type"%2C"%3D"%2C"out"]%2C["invoice"%2C"%3D"%2Cnull]]

   The supplier invoice lines can be seen by opening the main menu item:

      |Financial --> Invoices --> Supplier Invoices --> Lines|__

      .. |Financial --> Invoices --> Supplier Invoices --> Lines| replace:: :menuselection:`Financial --> Invoices --> Supplier Invoices --> Lines`
      __ https://demo.tryton.org/model/account.invoice.line;domain=[["invoice_type"%2C"%3D"%2C"in"]%2C["invoice"%2C"%3D"%2Cnull]]
