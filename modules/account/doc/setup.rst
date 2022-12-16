*****
Setup
*****

.. _Setting up the accounts structure:

Setting up the accounts structure
=================================

After you've activated the *Account Module* the module configuration will run
the `Create Chart <wizard-account.create_chart>` wizard and allow you to
create your `Company's <company:model-company.company>` accounts structure
from a template.
It is normally a good idea to do this at this point, if you can.

This will use the `Templates <concept-account.template>` from your selected
:guilabel:`Account Template` and create things like a Chart of
`Accounts <model-account.account>`,
the `Account Types <model-account.account.type>` used to generate the
balance sheet and income statements, and appropriate
`Taxes <model-account.tax>`, `Tax Codes <model-account.tax.code>`, and
`Tax Rules <model-account.tax.rule>` to go with them.

.. tip::

   If skipped running the *Create Chart* wizard you can always run it later
   from its main menu item.

.. _Creating a fiscal year:

Creating a fiscal year
======================

In order to be able to record any of your company's transactions in Tryton
you must first create a :ref:`Fiscal Year <model-account.fiscalyear>`.
This is because every account move happens during an accounting
:ref:`Period <model-account.period>`, and each period belongs to a fiscal
year.

You can create a new `Fiscal Year <model-account.fiscalyear>` from the
[:menuselection:`Financial --> Configuration --> Fiscal Years --> Fiscal Years`]
main menu item.

.. tip::

   The start and end of a fiscal year may align with a calendar year
   (1 January to 31 December) in which case it is common to use the year as
   its name.

   It is not essential that a fiscal year and calendar year align, in fact a
   fiscal year may be longer or shorter than a calendar year, depending on
   your country's legal requirements and financial reporting standards.

Once you have filled in the required information the
`Create Periods <wizard-account.fiscalyear.create_periods>` wizard allows you
to create a set of standard `Periods <model-account.period>`.
You should choose an appropriate period length for your
`Company <company:model-company.company>`, bearing in mind some reports are
generated based on periods, and periods allow you to build up your accounts in
smaller chunks.

.. tip::

   Tryton also provides easy ways of `Creating additional fiscal years`.
