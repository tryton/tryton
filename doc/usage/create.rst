.. _Creating additional fiscal years:

Creating additional fiscal years
================================

You will need a different `Fiscal Year <model-account.fiscalyear>` for each
year that you want to record accounting transactions.

You can create these in the same way as you
`created your initial fiscal year <Creating a fiscal year>`.

.. tip::

   An alternative, and often simpler, way of creating a new fiscal year is to
   use the `Renew Fiscal Year <wizard-account.fiscalyear.renew>` wizard.

.. _Creating journal entries:

Creating journal entries
========================

In Tryton `journal entries`_ are represented by
`Account Moves <model-account.move>`.
With the right modules activated Tryton will automatically create many of
the account moves for you.
However, there are times when you will need to manually move amounts from one
`Account <model-account.account>` to another.
You do this by using the items found under the
[:menuselection:`Financial --> Entries`] main menu item.

.. _journal entries: https://en.wikipedia.org/wiki/Journal_entry

One-off entries
---------------

For entries that are only needed once, for example to set an account's
initial opening balance, you can manually create an *Account Move*.

The [:menuselection:`Financial --> Entries --> Open Journal`] main menu item
provides another way of entering the details of an account move.
It provides a list of individual
`Account Move Lines <model-account.move.line>`, which can be added to as
required.

Reoccurring entries
-------------------

The best way to create accounting entries for things that are expected to
happen more than once is to use an
`Account Move Template <model-account.move.template>`.

You must first create the *Account Move Template* and set it up to ask for the
things that might change each time it is used.

You then run the
`Create Move from Template <wizard-account.move.template.create>` wizard to
create account moves based on a template of your choice.
