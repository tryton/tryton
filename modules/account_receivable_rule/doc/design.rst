******
Design
******

The *Account Receivable Rule* introduces the following concepts:


.. _model-account.account.receivable.rule:

Account Receivable Rule
=======================

The *Account Receivable Rule* defines how the amount posted on a temporary
receivable `Account <account:model-account.account>` are reconciled between
other receivable `Lines <account:model-account.move.line>` from accounts and
`Parties <party:model-party.party>`.
The rule provides different priority options for the lines.

.. note::

   If the :doc:`Account Dunning Module <account_dunning:index>` is activated,
   lines with blocked dunning are ignored.

.. note::

   If the :doc:`Account Statement Module <account_statement:index>` is
   activated, the rules defined for account of statement lines are applied when
   the statement is posted.

.. seealso::

   Account receivable rules can be found by opening the main menu item:

      |Financial --> Configuration --> General Account --> Account Receivable Rules|__

      .. |Financial --> Configuration --> General Account --> Account Receivable Rules| replace:: :menuselection:`Financial --> Configuration --> General Account --> Account Receivable Rules`
      __ https://demo.tryton.org/model/account.account.receivable.rule
