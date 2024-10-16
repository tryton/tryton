******
Design
******

The *Account Tax Cash Module* extends the following concepts:

.. _model-account.fiscalyear:

Fiscal Year
===========

When the *Account Tax Cash Module* is activated, the *Fiscal Year* is extended
to allow setting which `Tax Groups <account:model-account.tax.group>` are
reported on a cash basis for its periods.

.. seealso::

   The `Fiscal Year <account:model-account.fiscalyear>` concept is introduced
   by the :doc:`Account Module <account:index>`.

.. _model-account.period:

Period
======

When the *Account Tax Cash Module* is activated, the *Period* is extended to
allow setting which `Tax Groups <account:model-account.tax.group>` are reported
on a cash basis for that period.

When the *Period* is closed, a warning is raised if there are payment `Lines
<account:model-account.move.line>` that are not linked to an `Invoice
<account_invoice:model-account.invoice>`.

.. seealso::

   The `Period <account:model-account.period>` concept is introduced by the
   :doc:`Account Module <account:index>`.

.. _model-account.tax.line:

Tax Line
========

When the *Account Tax Cash Module* is activated, the *Tax Line* stores the
`Period <account:model-account.period>` in which it must be reported.
The *Period* is set automatically when a payment is linked to the `Invoice
<account_invoice:model-account.invoice>` that created the *Tax Line*.
If necessary, new *Tax Lines* are created proportionally to the amount of the
payment.
When a payment line is removed from an invoice, the reverse operation is
performed.

.. seealso::

   The `Tax Line <account:model-account.tax.line>` concept is introduced by the
   :doc:`Account Module <account:index>`.

.. _model-account.invoice:

Invoice
=======

When the *Account Tax Cash Module* is activated, supplier *Invoices* gain a
list of `Tax Groups <account:model-account.tax.group>` for which `Tax Lines
<model-account.tax.line>` must be reported on a cash basis.
This list is automatically populated from the invoice's `Party
<model-party.party>` property.

.. warning::
   The `Invoice <account_invoice:report-account.invoice>` report may need to be
   adjusted to include a legal notice when tax reporting on a cash basis is
   used.
   It can be tested with the ``on_cash_basis`` property of the invoice tax.

.. seealso::

   The `Invoice <account_invoice:model-account.invoice>` concept is introduced
   by the :doc:`Account Invoice Module <account_invoice:index>`.

.. _model-party.party:

Party
=====

When the *Account Tax Cash Module* is activated, *Parties* gain a new property
that allows setting which `Tax Groups <account:model-account.tax.group>` for
that supplier are reported on a cash basis.

.. seealso::

   The `Party <party:model-party.party>` concept is introduced by the
   :doc:`Party Module <party:index>`.
