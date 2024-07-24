******
Design
******

The *Account Cash Rounding Module* extends the following concepts:

.. _model-account.configuration:

Account Configuration
=====================

The *Account Configuration* is extended with a checkbox to round the cash
amounts and with two accounts to post the credited or debited amount due to the
rounding.

.. seealso::

   The `Account Configuration <account:model-account.configuration>` concept is
   introduced by the :doc:`Account Module <account:index>`.

.. _model-currency.currency:

Currency
========

When the *Account Cash Rounding Module* is activated, the *Currency* receives a
:guilabel:`Cash Rounding Factor` that represents the currency's smallest
available coin.

.. seealso::

   The `Currency <currency:model-currency.currency>` concept is introduced by
   the :doc:`Currency Module <currency:index>`.

.. _model-account.invoice:

Invoice
=======

When the *Account Cash Rounding Module* is activated, the *Invoice* receives a
:guilabel:`Cash Rounding` checkbox.
For customer invoices, the checkbox is automatically checked according to the
`Account Configuration <model-account.configuration>`.
For supplier invoices, it is up to the user to decide whether to check it or
not.
If the checkbox is checked then the total amount is rounded based on the
`Currency <currency:model-currency.currency>` and any remaining amount is
posted to the corresponding accounts found in the *Account Configuration*.

.. seealso::

   The `Invoice <account_invoice:model-account.invoice>` concept is introduced
   by the :doc:`Account Invoice Module <account_invoice:index>`.

.. _model-purchase.purchase:

Purchase
========

When the *Account Cash Rounding Module* is activated, the *Purchase* receives a
:guilabel:`Cash Rounding` checkbox which by default is set to the value of the
last purchase from the same supplier.
When the checkbox is checked then the total amount is rounded based on the
`Currency <currency:model-currency.currency>` and the *Purchase* transfers the
:guilabel:`Cash Rounding` setting to the created `Invoices
<account_invoice:model-account.invoice>`.

.. seealso::

   The `Purchase <purchase:model-purchase.purchase>` concept is introduced by
   the :doc:`Purchase Module <purchase:index>`.

.. _model-sale.sale:

Sale
====

When the *Account Cash Rounding Module* is activated, the *Sale* rounds the
total amount according to the `Account Configuration
<model-account.configuration>`.

.. seealso::

   The `Sale <sale:model-sale.sale>` concept is introduced by the :doc:`Sale
   Module <sale:index>`.
