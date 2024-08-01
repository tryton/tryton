******
Design
******

The *Analytic Account Module* introduces and extends the following concepts:

.. _model-analytic_account.account:

Analytic Account
================

The *Analytic Account* is used to represent the various analytical axes.
The *Analytic Accounts* are organized in a tree structure, with each root
defining an axis.

Only the *Analytic Accounts* of type :guilabel:`Normal` can be used with the
`Analytic Lines <model-analytic_account.line>`.

If an *Analytic Account* of the type :guilabel:`Distribution` is used in an
entry, an analytic line is created for each distribution line with an amount
proportional to its ratio and its *Analytic Account*.

.. seealso::

   The *Analytic Account* can be found by opening the main menu item:

   |Financial --> Configuration --> Analytic --> Accounts|__

   .. |Financial --> Configuration --> Analytic --> Accounts| replace:: :menuselection:`Financial --> Configuration --> Analytic --> Accounts`
   __ https://demo.tryton.org/model/analytic_account.account

.. _model-analytic_account.line:

Analytic Line
=============

The *Analytic Line* defines the amount from an `Account Move Line
<account:model-account.move.line>` to be allocated to an `Analytic Account
<model-analytic_account.account>`.

.. _model-account.move.line:

Account Move Line
=================

When the *Analytic Account Module* is activated, the *Account Move Line* gains
an :guilabel:`Analytic State` which is updated when the linked `Account Move
<account:model-account.move>` is posted.
The :guilabel:`Analytic State` is valid only if all the `Analytic Account
<model-analytic_account.account>` axes are completely filled.

.. seealso::

   The incomplete *Account Move Line* can be found by opening the main menu
   item:

   |Financial --> Processing --> Analytic Lines to Complete|__

   .. |Financial --> Processing --> Analytic Lines to Complete| replace:: :menuselection:`Financial --> Processing --> Analytic Lines to Complete`
   __ https://demo.tryton.org/model/account.move.line;domain=[["analytic_state"%2C"%3D"%2C"draft"]%2C["move_state"%2C"%3D"%2C"posted"]]

.. _model-analytic_account.rule:

Analytic Rule
=============

The *Analytic Rule* defines criteria such as `Account
<account:model-account.account>` and `Journal <account:model-account.journal>`
to automatically populate the empty `Analytic Lines
<model-analytic_account.line>` for a posted `Account Move
<account:model-account.move>`.

.. seealso::

   The *Analytic Rules* can be found by opening the main menu item:

   |Financial --> Configuration --> Analytic --> Rules|__

   .. |Financial --> Configuration --> Analytic --> Rules| replace:: :menuselection:`Financial --> Configuration --> Analytic --> Rules`
   __ https://demo.tryton.org/model/analytic_account.rule
