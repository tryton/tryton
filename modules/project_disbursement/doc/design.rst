******
Design
******

The *Project Disbursement Module* introduce some new concepts and extends some
existing concepts:

.. _model-account.configuration:

Configuration
=============

The *Project Configuration* gains new settings to configure the behavior of the
disbursement.

.. seealso::

   The `Project Configuration <project:model-project.configuration>` concept is
   introduced by the :doc:`Project Module <project:index>`.

.. _model-project.work:

Work Effort
===========

The *Work Effort* gains new properties to book `Disbursement
<model-project.disbursement>`.

.. seealso::

   The `Workf Effort <project:model-project.work>` concept is introduced by the
   :doc:`Project Module <project:index>`.

.. _concept-project.work.project:

Project
-------

The *Project* concept gains new properties to setup the `Account
<account:model-account.account>` and `Payment Journal
<account_payment:model-account.payment.journal>` for their `Disbursement
<model-project.disbursement>`.

.. seealso::

   The `Project <project:concept-project.work.project>` concept is introduced
   by the :doc:`Project Module <project:index>`.

.. _model-project.disbursement:

Disbursement
============

The *Disbursement* concept is used to manage payment made on behalf of the
`Party <party:model-party.party>` of the `Work Effort
<project:model-project.work>`.
Each disbursement, at any time, can be in one of several different states.
A disbursement progresses through these states unitl it is either
:guilabel:`Paid` or :guilabel:`Cancelled`.
`Payments <account_payment:model-account.payment>` are created when the
disbursement is validated.
Once a disbursement is paid, it is included in the invoice generated for the
`Project <project:concept-project.work.project>`.

.. seealso::

   Disbursements are found by opening the main menu item:

      |Projects --> Disbursements|__

      .. |Projects --> Disbursements| replace:: :menuselection:`Projects --> Disbursements`
      __ https://demo.tryton.org/model/project.disbursement


Account Configuration
=====================

When the *Project Disbursement Module* is activated, the *Account
Configuration* gains new properties such as the default account for
disbursement.

.. seealso::

   The `Account Configuration <account:model-account.configuration>` concept is
   introduced by the :doc:`Account Module <account:index>`.

.. _model-account.account.type:

Account Type
============

When the *Project Disbursement Module* is activated, the *Account Type* gains a
new property that indicates if any `Accounts <account:model-account.account>`
of this type can be used for disbursement.

.. seealso::

   The `Account Type <account:model-account.account.type>` concept is
   introduced by the :doc:`Account Module <account:index>`.
