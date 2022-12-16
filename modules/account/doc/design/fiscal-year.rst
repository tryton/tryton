.. _model-account.fiscalyear:

Fiscal Year
===========

In accounting the concept of a *Fiscal Year* is used when generating a
`Company's <company:model-company.company>` financial reports.
In Tryton it groups together a set of `Periods <model-account.period>`.

.. seealso::

   Fiscal years can be found by opening the main menu item:

      |Financial --> Configuration --> Fiscal Years --> Fiscal Years|__

      .. |Financial --> Configuration --> Fiscal Years --> Fiscal Years| replace:: :menuselection:`Financial --> Configuration --> Fiscal Years --> Fiscal Years`
      __ https://demo.tryton.org/model/account.fiscalyear

Wizards
-------

.. _wizard-account.fiscalyear.create_periods:

Create Periods
^^^^^^^^^^^^^^

For a *Fiscal Year*, the *Create Periods* wizard creates a set of monthly,
quarterly, or other fixed length periods.
The periods that are created cover the whole of the fiscal year, and do not
overlap.

.. _wizard-account.fiscalyear.renew:

Renew Fiscal Year
^^^^^^^^^^^^^^^^^

The *Renew Fiscal Year* wizard takes a previous *Fiscal Year* and lets the
user create a new fiscal year based on it.
When the wizard is started, by default, it is setup ready to create a new
fiscal year based on, and immediately following, the latest fiscal year.

.. seealso::

   The renew fiscal year wizard can be started from the main menu item:

      :menuselection:`Financial --> Configuration --> Fiscal Years --> Renew Fiscal Year`

.. _wizard-account.fiscalyear.balance_non_deferral:

Balance Non-Deferral
^^^^^^^^^^^^^^^^^^^^

At the fiscal year-end the *Balance Non-Deferral* wizard is used to
create `Account Moves <model-account.move>` that zero the balances of each
non-deferral `Account <model-account.account>` using a counterpart account.

.. seealso::

   The balance non-deferral wizard is started using the main menu item:

      :menuselection:`Financial --> Processing --> Balance Non-Deferral`

.. _model-account.period:

Period
======

An accounting *Period* represents a period of time between two dates.
It allows a `Company's <company:model-company.company>` accounts to be
processed, aggregated and analysed based on this fixed range of time.
Each period in Tryton belongs to a `Fiscal Year <model-account.fiscalyear>`.

There are two different types of period, standard periods, and
adjustment periods.
Standard periods from the same fiscal year cannot overlap, and by default
Tryton will only use Standard periods when creating new
`Account Moves <model-account.move>`.
Adjustment periods are typically used for things like the
accounting moves created when `Closing a fiscal year`, and these periods may
overlap other periods.

.. seealso::

   Periods can be found by opening the main menu item:

      |Financial --> Configuration --> Fiscal Years --> Fiscal Years --> Periods|__

      .. |Financial --> Configuration --> Fiscal Years --> Fiscal Years --> Periods| replace:: :menuselection:`Financial --> Configuration --> Fiscal Years --> Fiscal Years --> Periods`
      __ https://demo.tryton.org/model/account.period
