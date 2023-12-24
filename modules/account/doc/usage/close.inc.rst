.. _Closing a period:

Closing a period
================

To help you keep your accounts tidy, and help you avoid errors, Tryton lets you
close each of your `Company's <company:model-company.company>` accounting
`Periods <model-account.period>` as soon as they are finished.

Check everything is ready
-------------------------

Before you go ahead and close the period it is a good idea to check that
you have recorded all the transactions related to the period in Tryton.
This includes any `Account Moves <model-account.move>` that are needed for
things like prepayments, accruals or depreciation.
You may also want to check that things like bank balances reconcile, and
account moves have been posted.

.. tip::

   If you are not ready to close the period, but want to restrict which
   `Journals <model-account.journal>` are still open then you can partially
   close a period.
   In Tryton this is done by using the
   [:menuselection:`Financial --> Processing --> Close Journals - Periods`]
   main menu item.

Close the period
----------------

Once you are happy everything seems to be okay you use the
[:menuselection:`Financial --> Processing --> Close Periods`] main menu item
to close the period.

.. note::

   Many companies will also have their own additional processes which need
   to be run at period end.
   These may include things like generating reports, and reporting taxes.

.. tip::

   If you need to make changes to a closed period you can re-open it, unless
   it has been locked.

   To re-open a closed period use the
   [:menuselection:`Financial --> Processing --> Close Periods`] menu item.
   To find a closed period, you will need to clear the filter so that all the
   periods are listed, not just the open ones.

.. _Closing a fiscal year:

Closing a fiscal year
=====================

There are several steps you need to follow in order to close a
`Fiscal Year <model-account.fiscalyear>` in Tryton.

Check everything is ready
-------------------------

To help you prepare to close the fiscal year you will often want to first
ensure all its `Periods <model-account.period>` are closed, by following your
normal procedures for `Closing a period`.

Now is also a good time to double check that you haven't forgotten anything,
and ensure that there are no obvious errors, or anomalies.

Reset non-deferral accounts
---------------------------

Next, you need to move the balances of all the non-deferral `Accounts
<model-account.account>` (also known as nominal or temporary accounts) to an
appropriate deferral account (also known as real or permanent account).
The best way to do this is to use the `Balance Non-Deferral
<wizard-account.fiscalyear.balance_non_deferral>` wizard.

.. tip::

   When using the balance non-deferral wizard, you should create an adjustment
   period for the year end closing entries.
   It is best practice to use the last day of the fiscal year as both the
   start and end date for this period.

.. tip::

   The first time you use the balance non-deferral wizard, you may need to
   create a special ``Situation`` `Journal <model-account.journal>` for
   the year end closing entries.

Create other year end entries
-----------------------------

With the initial closing entries created you can now go ahead and create any
other moves that are required by the accounting processes of your country.
These will be moves for things like taxes on revenue, dividends, and so on.
When creating these you may want to use the adjustment period you used in
the last step.

Close the fiscal year
---------------------

Finally once all the year end and closing moves have been posted you can close
the fiscal year from the
[:menuselection:`Financial --> Processing --> Close Fiscal Year`] menu item.
