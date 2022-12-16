******
Design
******

The *Account Invoice Defer Module* adds some new concepts and extends some
existing concepts.

.. _model-account.invoice.deferred:

Invoice Deferred
================

*Invoice Deferred* defines the periods over which an `Invoice
<account_invoice:model-account.invoice>` Line and its amount is deferred.

When running the extra amount booked of the invoice period is moved to
configured deferral account.
And the corresponding amount is moved to each existing standard `Period
<account:model-account.period>` inside the deferral period.

The amount of each period is computed using a daily rate and the number of days
in the period.

.. seealso::

   Customer invoices deferred can be seen by opening the main menu item:

      |Financial --> Invoices --> Customer Invoices Deferred|__

      .. |Financial --> Invoices --> Customer Invoices Deferred| replace:: :menuselection:`Financial --> Invoices --> Customer Invoices Deferred`
      __ https://demo.tryton.org/model/account.invoice.deferred;domain=[["type"%2C"%3D"%2C"out"]]

   Supplier invoices deferred can be seen by opening the main menu item:

      |Financial --> Invoices --> Supplier Invoices Deferred|__

      .. |Financial --> Invoices --> Supplier Invoices Deferred| replace:: :menuselection:`Financial --> Invoices --> Supplier Invoices Deferred`
      __ https://demo.tryton.org/model/account.invoice.deferred;domain=[["type"%2C"%3D"%2C"in"]]

Wizards
-------

.. _wizard-account.invoice.deferred.create_moves:

Invoice Deferred Create Moves
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The *Invoice Deferred Create Moves* wizard creates and posts for each running
`Invoice Deferred <model-account.invoice.deferred>` the missing moves for each
standard `Period <account:model-account.period>`.
It closes also the invoices deferred if all the moves have been posted.
