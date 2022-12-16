******
Design
******

The *Company Module* introduces some new concepts, and extends other existing
concepts:

.. _model-company.company:

Company
=======

The *Company* is the main concept provided by the *Company Module*.
In Tryton it is a `Party <party:model-party.party>` that represents the
company, or organisation, which the users of the system are members of.

.. seealso::

   Companies can be found by opening the main menu item:

      |Companies --> Companies|__

      .. |Companies --> Companies| replace:: :menuselection:`Companies --> Companies`
      __ https://demo.tryton.org/model/company.company

.. _model-company.employee:

Employee
========

The *Employee* is another important concept introduced by the *Company Module*.
In Tryton it is a `Party <party:model-party.party>` that is employed by, or
works for, one of the `Companies <model-company.company>` which the users are
members of.

Employees can be organised into a structure by setting each employee's
supervisor.

.. seealso::

   A list of the employees for all the companies can be found from the main
   menu item:

      |Companies --> Employees|__

      .. |Companies --> Employees| replace:: :menuselection:`Companies --> Employees`
      __ https://demo.tryton.org/model/company.employee

.. _model-res.user:

User
====

The *Company Module* extends the *User* concept so that each user can be
associated with one or more `Companies <model-company.company>` and a set of
`Employees <model-company.employee>`.
From these a user then `chooses a current company and employee
<Setting your current company and employee>`.

This choice directly affects what data the user has access to in Tryton,
as models will often link records to a company and restrict access based on
the user's setup.

.. seealso::

   The *User* concept is introduced by the ``res`` module.

.. _model-party.party:

Party
=====

The *Company Module* adds an addition report that can be used with
`Parties <party:model-party.party>`.

.. seealso::

   The *Party* concept is introduced by the :doc:`Party Module <party:index>`.

Reports
-------

.. _report-party.letter:

Letter
^^^^^^

This report is a document that can be used as the starting point for a letter
to the selected `Party <party:model-party.party>`.
The letter that is created is preformatted with information about the party,
the *User* and the user's current `Company <model-company.company>`.
The only thing that then needs to be added is the main contents of the letter.
