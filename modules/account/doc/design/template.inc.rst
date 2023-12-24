.. _concept-account.template:
.. _model-account.account.template:
.. _model-account.account.type.template:
.. _model-account.tax.template:
.. _model-account.tax.code.template:
.. _model-account.tax.rule.template:

Templates
=========

The *Templates* are used to predefine a set of basic accounting structures
and rules.
The templates have the same properties as their non-template equivalents
except they are not linked to a `Company <company:model-company.company>`.

There are templates for:

* `Accounts <model-account.account>`,
* `Account Types <model-account.account.type>`,
* `Taxes <model-account.tax>`,
* `Tax Codes <model-account.tax.code>`, and
* `Tax Rules <model-account.tax.rule>`.

These templates are used together to form a complete accounting structure for
particular country and/or company type.

.. seealso::

    The templates can be found using the following menu entries:

    * |Financial --> Configuration --> Templates --> Account Types|__
    * |Financial --> Configuration --> Templates --> Accounts|__
    * |Financial --> Configuration --> Templates --> Tax Codes|__
    * |Financial --> Configuration --> Templates --> Taxes|__
    * |Financial --> Configuration --> Templates --> Tax Rules|__

    .. |Financial --> Configuration --> Templates --> Account Types| replace:: :menuselection:`Financial --> Configuration --> Templates --> Account Types`
    __ https://demo.tryton.org/model/account.account.type.template
    .. |Financial --> Configuration --> Templates --> Accounts| replace:: :menuselection:`Financial --> Configuration --> Templates --> Accounts`
    __ https://demo.tryton.org/model/account.account.template
    .. |Financial --> Configuration --> Templates --> Tax Codes| replace:: :menuselection:`Financial --> Configuration --> Templates --> Tax Codes`
    __ https://demo.tryton.org/model/account.tax.code.template
    .. |Financial --> Configuration --> Templates --> Taxes| replace:: :menuselection:`Financial --> Configuration --> Templates --> Taxes`
    __ https://demo.tryton.org/model/account.tax.template
    .. |Financial --> Configuration --> Templates --> Tax Rules| replace:: :menuselection:`Financial --> Configuration --> Templates --> Tax Rules`
    __ https://demo.tryton.org/model/account.tax.rule.template

Wizards
-------

.. _wizard-account.create_chart:

Create Chart
^^^^^^^^^^^^

The *Create Chart* wizard takes a set of templates and creates the
corresponding accounts structure for a single
`Company <company:model-company.company>`.
This includes structures like the chart of accounts, balance sheet and income
statement, and taxes and related tax management and reporting structures.

.. seealso::

   The create chart wizard can be started from the main menu item:

      :menuselection:`Financial --> Configuration --> Templates --> Create Chart of Account from Template`

.. _wizard-account.update_chart:

Update Chart
^^^^^^^^^^^^

The *Update Chart* wizard updates a `Company's <company:model-company.company>`
accounts structure with any changes that have been made to the underlying
templates.

.. seealso::

   The update chart wizard can be started from the main menu item:

      :menuselection:`Financial --> Configuration --> Templates --> Update Chart of Account from Template`

.. _model-account.move.template:

Account Move Template
=====================

An *Account Move Template* provides a predefined structure for an
`Account Move <model-account.move>`.

Each account move template can define a set of keywords.
Values for these keywords are requested from the user when the template is
used.
These values are then substituted for the keyword placeholders defined in the
account move template's fields.

The account move template's lines, and their tax lines, mirror the structure of
`Account Move Lines <model-account.move.line>` and
`Tax Lines <model-account.tax.line>` respectively.
However, in selected fields they also allow the use of expressions that can
contain the keyword placeholders.

.. seealso::

   The account move templates can be found by using the main menu item:

      |Financial --> Configuration --> Templates --> Account Move Template|__

      .. |Financial --> Configuration --> Templates --> Account Move Template| replace:: :menuselection:`Financial --> Configuration --> Templates --> Account Move Template`
      __ https://demo.tryton.org/model/account.move.template

Wizards
-------

.. _wizard-account.move.template.create:

Create Move
^^^^^^^^^^^

The *Create Move* wizard is used to create a new
`Account Move <model-account.move>` based on a selected
`Move Template <model-account.move.template>`.

.. seealso::

   The create move wizard can be started from the main menu item:

      :menuselection:`Financial --> Entries --> Create Move from Template`
