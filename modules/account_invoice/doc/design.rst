Design
******

The *Account Invoice Module* adds some new concepts and extends some existing
concepts.

.. _model-account.invoice:

Invoice
=======

The main concept introduced by the *Account Invoice Module* is the *Invoice*.
This contains details of a purchase, or sales, transaction between the
`Company <company:model-company.company>` and another
`Party <party:model-party.party>`.

Each invoice has a type that indicates whether it is an invoice from a
supplier, or to a customer.
Credit notes are represented by invoices with negative totals.

Additional information is also stored for each invoice, including things like
a unique `Sequence <model-account.fiscalyear.invoice_sequence>` number,
invoice, accounting and payment term dates,
`Payment Terms <model-account.invoice.payment_term>`,
`Tax Identifiers <party:model-party.identifier>`,
`Currency <currency:model-currency.currency>` information,
the customer's or supplier's invoice `Address <party:model-party.address>`,
and other descriptions and reference numbers.

An invoice is made up from one, or more, invoice lines.
Most lines normally contain information about the items that were bought or
sold, including information about the `Products <product:concept-product>`,
quantities, `Taxes <account:model-account.tax>` and prices that make up the
transaction.
There are also some types of line that add other information like titles,
descriptions or subtotals.

The taxes that are included on an invoice are calculated from the tax
amounts for each of the invoice's lines.
These amounts are rounded at either the line or invoice level depending on the
setting in the `Account Configuration <account:model-account.configuration>`.
Additional taxes can be manually added to the invoice when required.
It is also possible to change calculated tax amounts, although these changes
get overwritten if the invoice's tax amounts get recalculated.
For supplier invoice it is possible to define per line the deductible rate of
the taxes.

When an invoice is processed an `Account Move <account:model-account.move>` is
automatically created for it.
This account move records the transaction represented by the invoice and
places the total in the specified payable or receivable
`Account <account:model-account.account>`.

.. note::

   For customer invoices the `Invoice Report <report-account.invoice>` is
   generated and stored at the point when the invoice is posted.

.. seealso::

   Customer invoices and credit notes can be seen by opening the main menu
   item:

      |Financial --> Invoices --> Customer Invoices|__

      .. |Financial --> Invoices --> Customer Invoices| replace:: :menuselection:`Financial --> Invoices --> Customer Invoices`
      __ https://demo.tryton.org/model/account.invoice;domain=[["type"%2C"%3D"%2C"out"]]

   Supplier invoices and credit note are available from the main menu item:

      |Financial --> Invoices --> Supplier Invoices|__

      .. |Financial --> Invoices --> Supplier Invoices| replace:: :menuselection:`Financial --> Invoices --> Supplier Invoices`
      __ https://demo.tryton.org/model/account.invoice;domain=[["type"%2C"%3D"%2C"in"]]

Wizards
-------

.. _wizard-account.invoice.pay:

Pay Invoice
^^^^^^^^^^^

The *Pay Invoice* wizard allows a cash payment for an invoice to be registered
against the invoice.
It uses the values from an
`Invoice Payment Method <model-account.invoice.payment.method>` when creating
the `Account Move <account:model-account.move>`.
The wizard supports partial payments, and can also be used to write-off some
of the invoice amount.

.. _wizard-account.invoice.credit:

Credit Invoice
^^^^^^^^^^^^^^

The *Credit Invoice* wizard enables a credit note to be raised for the
selected invoices.

For customer invoices that are posted, the wizard allows the invoice to be
credited with a refund.
When this is done the credit note is automatically posted and the invoice is
cancelled.

.. _wizard-account.invoice.lines_to_pay.reschedule:

Reschedule Lines to Pay
^^^^^^^^^^^^^^^^^^^^^^^

The *Reschedule Lines to Pay* wizard allows to modify the payment terms of the
remaining lines to pay using the `Reschedule Lines
<wizard-account.move.line.reschedule>` wizard.

Reports
-------

.. _report-account.invoice:

Invoice
^^^^^^^

The *Invoice* report is used to output a hard copy of the invoice or credit
note.
It includes all the information that is needed in order to send the document
to a customer or supplier.

.. _model-account.invoice.payment.method:

Invoice Payment Method
======================

The concept of an *Invoice Payment Method* brings together an
`Account Journal <account:model-account.journal>`,
a debit `Account <account:model-account.account>` and a credit account.
This is normally used during the `Pay Invoice <wizard-account.invoice.pay>`
wizard.

.. seealso::

   Invoice payment methods can be found using the main menu item:

      |Financial --> Configuration --> Journals --> Invoice Payment Methods|__

      .. |Financial --> Configuration --> Journals --> Invoice Payment Methods| replace:: :menuselection:`Financial --> Configuration --> Journals --> Invoice Payment Methods`
      __ https://demo.tryton.org/model/account.invoice.payment.method

.. _model-account.fiscalyear.invoice_sequence:

Fiscal Year Invoice Sequence
============================

The *Fiscal Year Invoice Sequence* concept allows a set of *Sequences* to be
defined for use with `Invoices <model-account.invoice>`.
It allows different sequences to be used for each of the different types of
invoices and credit notes.
It also allows the use of different sequences for each accounting
`Period <account:model-account.period>`.

.. seealso::

   The fiscal year sequences are defined in the
   `Fiscal Year <account:model-account.fiscalyear>`.

.. _model-account.invoice.payment_term:

Payment Term
============

The *Payment Term* stores the method that is used to calculate an
`Invoice's <model-account.invoice>` payment due dates.

An invoice may be due for payment in full on a particular day, or may become
due for payment over time in parts.

To allow for this each payment term is made up of one or more lines.
Each line defines an amount that should be paid, and when that payment is
expected.
The amounts can be defined as either fixed amounts, percentages, or a
remainder.

.. seealso::

   Payment terms are create and managed from the main menu item:

      |Financial --> Configuration --> Payment Terms --> Payment Terms|__

      .. |Financial --> Configuration --> Payment Terms --> Payment Terms| replace:: :menuselection:`Financial --> Configuration --> Payment Terms --> Payment Terms`
      __ https://demo.tryton.org/model/account.invoice.payment_term

Wizards
-------

.. _wizard-account.invoice.payment_term.test:

Test Payment Term
^^^^^^^^^^^^^^^^^

The *Test Payment Term* wizard shows how a specific invoice amount is
broken down for a particular
`Payment Term <model-account.invoice.payment_term>`.
It allows a date and an amount to be entered and then calculates the due dates
and amounts for each payment that will be required for that payment term.

.. seealso::

   Payment terms can be tested out by opening the main menu item:

      :menuselection:`Financial --> Configuration --> Payment Terms --> Test Payment Term`
