.. _Setting a party's invoice address:

Setting a party's invoice address
=================================

Tryton lets you mark which `Addresses <party:model-party.address>`, and
also `Contact Mechanisms <party:model-party.contact_mechanism>`, should be
used with `Invoices <model-account.invoice>`.

.. tip::

   If you don't set an invoice addresses or contact mechanisms, then the
   party's first address or contact mechanism is used.

.. _Setting default accounts:

Setting default accounts
========================

Receivable and payable
^^^^^^^^^^^^^^^^^^^^^^

You can set the default receivable and payable
`Accounts <account:model-account.account>` that are used for the invoice
totals, for customers and suppliers respectively, in the
`Account Configuration <account:model-account.configuration>`.

A `Party <party:model-party.party>` can override these default accounts
and normally allows you to set which accounts you want to use with that party.

Revenue and Expense
^^^^^^^^^^^^^^^^^^^

The default revenue and expense accounts for the
`Products <product:concept-product>` that appear on the invoice's lines are
also set in the *Account Configuration*.

These default accounts are used unless the product overrides them.
Normally this is done by setting the revenue and expense accounts in the
product's `Account Category <account_product:model-product.category>`.

Tax
^^^

The accounts that are used for any `Taxes <account:model-account.tax>` are set
on the taxes themselves.

.. _Creating payment terms:

Creating payment terms
======================

Any `Payment Term <model-account.invoice.payment_term>` that you want to use
must be created before you can use them.
You can do this at the point where you need to use them, or beforehand.

The payment term defines when payment for an `Invoice <model-account.invoice>`
is expected.
Each part of a payment term allows you specify an amount and a date by adding
months, weeks and days to the invoice date, and also setting a day of the
month, month of the year, or day of the week that the payment is due.
This calculation is done using |python-dateutil's relativedeltas|__.

.. |python-dateutil's relativedeltas| replace:: python-dateutil's ``relativedeltas``
__ https://dateutil.readthedocs.io/en/stable/relativedelta.html

One payment term that is sometimes used is "30 Days", this means you expect
payment 30 days after the date on the invoice.
In Tryton you would set this up by creating a payment term like this::

   Name: 30 Days
   Line 1:
      Type: Remainder
      Number of Days: 30

You may want to request payment at the end of the month that the invoice
was raised in, you can do this with::

   Name: End Of Month
   Line 1:
      Type: Remainder
      Day of Month: 31

You can also define payment terms in which the payment is expected in stages.
For example, to require a fixed amount of 100 immediately, then 50% of what
is left after 7 days and the remaining amount after 14 days you would use::

   Name: Payment in Stages
   Line 1:
      Type: Fixed
      Amount: 100
      Number of Days: 0
   Line 2:
      Type: Percentage on Remainder
      Ratio: 50%
      Number of Days: 7
   Line 3:
      Type: Remainder
      Number of Days: 14

.. tip::

    For complex payment terms if you want to check what dates and amounts
    it will generate you can try it out using the
    `Test Payment Term <wizard-account.invoice.payment_term.test>` wizard.
