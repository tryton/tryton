******
Design
******

The *Account Export WinBooks Module* extends the following concepts:

.. _model-account.move.export:

Account Move Export
===================

When the *Account Export WinBooks Module* is activated, move exports gain a new
type :guilabel:`WinBooks`.
When the type *WinBooks* is selected, the export generates a `ZIP file
<https://en.wikipedia.org/wiki/ZIP_(file_format)>`_ that contains the file:

   - :file:`ACT.txt`

.. seealso::

   The `Account Move Export <account_export:model-account.move.export>` concept
   is introduced by the :doc:`Account Export Module <account_export:index>`.

.. _model-account.account:

Account
=======

When the *Account Export WinBooks Module* is activated, accounts gain a new
field :guilabel:`WinBooks Code` to replace the account code in export.

.. seealso::

   The `Account <account:model-account.account>` concept is introduced by the
   :doc:`Account Module <account:index>`.

.. _model-account.fiscalyear:

Fiscal Year
===========

When the *Account Export WinBooks Module* is activated, fiscal years gain a new
field :guilabel:`WinBooks Code`.

.. seealso::

   The `Fiscal Year <account:model-account.fiscalyear>` concept is introduced
   by the :doc:`Account Module <account:index>`.

Wizards
-------

.. _wizard-account.fiscalyear.renew:

Renew Fiscal Year
^^^^^^^^^^^^^^^^^

When the *Account Export WinBooks Module* is activated, the :guilabel:`WinBooks
Code` is updated based on the previous *Fiscal Year*.

.. seealso::

   The `Renew Fiscal Year <account:wizard-account.fiscalyear.renew>` concept is
   introduced by the :doc:`Account Module <account:index>`.

.. _model-account.journal:

Journal
=======

When the *Account Export WinBooks Module* is activated, journals gain new
fields :guilabel:`WinBooks Code` and :guilabel:`WinBooks Code Credit Note`.

.. seealso::

   The `Journal <account:model-account.journal>` concept is introduced by the
   :doc:`Account Module <account:index>`.

.. _model-party.identifier:

Party Identifier
================

When the *Account Export WinBooks Module* is activated, party identifier gain
two new types :guilabel:`WinBooks Supplier` and :guilabel:`WinBooks Customer`.

.. seealso::

   The `Party Identifier <party:model-party.identifier>` concept is introduced
   by the :doc:`Party Module <party:index>`.
