******
Design
******

The *Account ES SII Module* introduces the following concepts:

.. _model-account.invoice.sii:

SII Invoice
===========

The main concept introduced by the *Account ES SII Module* is the *SII Invoice*.
It relates a `Invoice <account_invoice:model-account.invoice>` with it
state in the :abbr:`SII (Immediate Information Service)`.
A record is automatically created when an invoices that should be sent to SII
is posted.

When the invoice is correctly set it stores the secure validation code of
the delivery.
If there are any error with the invoice, the error code and description are
stored.

.. seealso::

   The SSI Invoices can be foun by opening the main menu item:

      |Financial --> Invoices --> SII Invoices|__

      .. |Financial --> Invoices --> SII Invoices| replace:: :menuselection:`Financial --> Invoices --> SII Invoices`
      __ https://demo.tryton.org/model/account.invoice.sii
