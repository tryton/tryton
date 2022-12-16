.. _Invoicing customers:

Invoicing customers
===================

If your `Company <company:model-company.company>` has sold some things and
you want to issue an invoice to the customer, then in Tryton you need to
create a customer `Invoice <model-account.invoice>`.

.. tip::

   Tryton provides additional modules that can be used to automatically create
   customer invoices.
   These modules normally create draft invoices for you with almost all the
   data already filled in.

If you need to manually create a new customer `Invoice <model-account.invoice>`
you will need to enter in a few details such as the name of the
`Party <party:model-party.party>`, the
`Currency <currency:model-currency.currency>` and the lines that make up the
invoice.
Most of the other fields are optional or have sensible default values.

.. tip::

   If the invoice you want to create is almost the same as an existing
   invoice then you can use the :guilabel:`Duplicate` item from the form's
   menu to avoid creating it from scratch.

You should post the invoice before you issue it to your customer.
Once the invoice has been posted the `Invoice report <report-account.invoice>`
can be printed out or saved, and sent to your customer.

.. tip::

   The *Invoice report* generates a *Pro forma invoice* for invoices that are
   validated, but not yet posted.

.. tip::

   The *Invoice report* is saved for posted customer invoices.
   This means that every time you print it you will get an identical copy
   of it.

.. _Handling supplier invoices:

Handling supplier invoices
==========================

Supplier `Invoices <model-account.invoice>` are issued to your
`Company <company:model-company.company>` by a supplier for things that you
purchase.

For each invoice that you receive you need a new supplier invoice in Tryton.

.. tip::

   Tryton provides additional modules that automatically create, or help
   create, supplier invoices.
   If you are using these modules then the supplier invoices or invoice lines
   are often automatically created for you.

.. tip::

   If the invoice you want to create is almost the same as an existing
   invoice then you can use the :guilabel:`Duplicate` item from the form's
   menu to avoid creating it from scratch.

Once you have created, or found, the supplier invoice on Tryton you should
check that it matches the one provided by the supplier.
If you see any differences due to the way the taxes have been calculated
then these can be fixed once all the lines are entered.
You can do this by manually changing the tax amounts on the supplier invoice
on Tryton.

When you are happy the supplier invoice is correct, and it matches the one
on Tryton you can post it.

.. _Paying an invoice:

Paying an invoice
=================

Each `Invoice <model-account.invoice>` tracks how much still needs to be paid.
Once an invoice has been fully paid it automatically updates its state to
indicate that it is now paid.

If you are manually registering payments against invoices, then you can use
the invoice's :guilabel:`Pay` button to run the
`Pay Invoice <wizard-account.invoice.pay>` wizard and register a cash payment
against the invoice.

When doing this you will need to have already setup an appropriate
`Invoice Payment Method <model-account.invoice.payment.method>`.
This then makes it easy to use consistent
`Journals <account:model-account.journal>` and
`Accounts <account:model-account.account>` when manually entering payments.

.. note::

   Some of the other accounting modules allow you to automatically register
   payments against invoices.
   So, if you are using those modules you will not normally need to do this
   manually.
