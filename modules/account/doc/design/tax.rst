.. _model-account.tax:

Tax
===

The *Tax* concept allows the taxes a `Company <company:model-company.company>`
uses to be represented in Tryton.
Taxes can be for a fixed amount, or a percentage of an item's price.
The tax can also be setup to be included as part of an item's price for any
later taxes that get applied, resulting in it being compounded by these later
taxes.

A date range can be used to restrict when a tax applies.

Applying a tax will also apply all of its children.

.. seealso::

   The taxes can be found by opening the main menu item:

      |Financial --> Configuration --> Taxes --> Taxes|__

      .. |Financial --> Configuration --> Taxes --> Taxes| replace:: :menuselection:`Financial --> Configuration --> Taxes --> Taxes`
      __ https://demo.tryton.org/model/account.tax

   Taxes can be created from `Tax Templates <model-account.tax.template>`.

Wizards
-------

.. _wizard-account.tax.test:

Test Tax
^^^^^^^^

The *Test Tax* wizard allows a user to test how different taxes get applied.
It does this without altering any data on the system, and lets the user
instantly see the result of applying different taxes.

.. seealso::

   The test tax wizard can be started using the main menu item:

      :menuselection:`Financial --> Configuration --> Taxes --> Test Tax`

.. _model-account.tax.line:

Tax Line
========

The *Tax Line* concept is used to record how an
`Account Move Line <model-account.move.line>` is split up for tax purposes.
Each tax line represents a tax amount, or base amount, for a specific
*Account Move Line* and `Tax <model-account.tax>` combination.

.. _model-account.tax.group:

Tax Group
=========

The *Tax Group* concept is used to group together `Taxes <model-account.tax>`
of the same type.
These tax groups can then be used in `Tax Rules' <model-account.tax.rule>`
lines to change which taxes are applied to an item.

.. seealso::

   The tax groups can be found using the main menu item:

      |Financial --> Configuration --> Taxes --> Tax Groups|__

      .. |Financial --> Configuration --> Taxes --> Tax Groups| replace:: :menuselection:`Financial --> Configuration --> Taxes --> Tax Groups`
      __ https://demo.tryton.org/model/account.tax.group

.. _model-account.tax.rule:

Tax Rule
========

A *Tax Rule* allows taxes to be substituted for other taxes based on a set of
rules.
When the tax rule is applied the rule defined by its first matching line is
used.

The tax rule's lines contain a set of properties, such as the
`Tax <model-account.tax>`, its `Group <model-account.tax.group>`, or a date
range.
These are used to work out if the tax rule line matches the tax.
If the tax matches, then a substitution tax is added and the origin tax is
removed, unless the tax rule line indicates that the origin tax should also
be kept.

.. seealso::

   The available tax rules can be found by opening the main menu item:

      |Financial --> Configuration --> Taxes --> Tax Rules|__

      .. |Financial --> Configuration --> Taxes --> Tax Rules| replace:: :menuselection:`Financial --> Configuration --> Taxes --> Tax Rules`
      __ https://demo.tryton.org/model/account.tax.rule

   Tax rules can be created from
   `Tax Rule Templates <model-account.tax.rule.template>`.

.. _model-account.tax.code:

Tax Code
========

In Tryton *Tax Codes* are used to collect together tax amounts and base amounts
for tax reporting.

Each tax code is made up from lines, each of which collect together either the
tax or base amounts for a specific `Tax <model-account.tax>` and type of
transaction.
An operator then allows this value to be negated if required.

The tax codes can be placed into a structure with each having a parent and
some children.

The amounts shown by each tax code are based on the values from tax code's
lines, and the amounts provided by the tax code's children.

.. seealso::

   The list of tax codes can be found using the main menu item:

      |Financial --> Configuration --> Taxes --> Tax Codes --> Tax Codes|__

      .. |Financial --> Configuration --> Taxes --> Tax Codes --> Tax Codes| replace:: :menuselection:`Financial --> Configuration --> Taxes --> Tax Codes --> Tax Codes`
      __ https://demo.tryton.org/model/account.tax.code

   Tax codes can be created from
   `Tax Code Templates <model-account.tax.code.template>`.
