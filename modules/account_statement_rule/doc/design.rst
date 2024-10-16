******
Design
******

The *Account Statement Rule Module* introduces and extends the following
concepts:

.. _model-account.statement:

Statement
=========

When the *Account Statement Rule Module* is activated, the *Statement* gains an
:guilabel:`Apply Rules` button.
This button uses the `Statement rules <model-account.statement.rule>` to create
statement lines for any of the origins that match a rule.

.. seealso::

   The `Statement <account_statement:model-account.statement>` concept is
   introduced by the :doc:`Account Statement Module <account_statement:index>`.

.. _model-account.statement.rule:

Statement Rule
==============

The *Statement Rule* consists of an ordered set of criteria such as amount,
journal, description pattern etc. to match against the statement origins.
The first rule that matches is used to create statement lines using its lines
as a template.

.. seealso::

   The Statement Rules can be found by opening the main menu item:

   |Financial --> Configuration --> Statements --> Rules|__

   .. |Financial --> Configuration --> Statements --> Rules| replace:: :menuselection:`Financial --> Configuration --> Statements --> Rules`
   __ https://demo.tryton.org/model/account.statement.rule
