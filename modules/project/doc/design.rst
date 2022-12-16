******
Design
******

The *Project Module* introduces some new concepts and extends some existing
concepts:

.. _model-project.work:

Work Effort
===========

The *Work Effort* concept is used to represent work that must be done for
projects, or parts of projects.

Each *Work Effort* is described by a name and a type, and there is space
for additional comments to be added when required.

The estimated time and effort needed for the work is recorded, and it is also
possible to track the actual time and effort required.

If timesheets are selected to be used, then the time spent on the work can
be recorded by `Employees <company:model-company.employee>` by creating
:doc:`Timesheet Lines <timesheet:index>` with the right :doc:`Timesheet Works
<timesheet:index>`.
The *Timesheet Works* for the *Work Efforts* are automatically created and
deleted as needed.

The current progress of a project's work and its
`Work Status <model-project.work.status>` is also recorded.

A project's work can be structured by giving work efforts a parent and some
children, if required.

Each *Work Effort* has a type.
Once a work effort has been created it can be changed to a different type
if its scope, or the amount of work required, changes.

.. seealso::

   Work efforts can be found by opening the main menu item:

      |Projects --> Configuration --> Works Efforts|__

      .. |Projects --> Configuration --> Works Efforts| replace:: :menuselection:`Projects --> Configuration --> Works Efforts`
      __ https://demo.tryton.org/model/project.work

.. _concept-project.work.project:

Project
-------

A *Project* is a type of *Work Effort* that is used for larger and more
complex work.

It can have a `Party <party:model-party.party>` and
`Party Address <party:model-party.address>`.
These are used to record who the project is for.

.. seealso::

   A list of projects can be found using the main menu item:

      |Projects --> Projects|__

      .. |Projects --> Projects| replace:: :menuselection:`Projects --> Projects`
      __ https://demo.tryton.org/model/project.work;name="Projects"&domain=[["type"%2C"%3D"%2C"project"]]

.. _concept-project.work.task:

Task
----

A *Task* is a type of *Work Effort* that is used for smaller pieces of work.

.. seealso::

   A list of tasks can be found using the main menu item:

      |Projects --> Tasks|__

      .. |Projects --> Tasks| replace:: :menuselection:`Projects --> Tasks`
      __ https://demo.tryton.org/model/project.work;name="Tasks"&domain=[["type"%2C"%3D"%2C"task"]]

.. _model-project.work.status:

Work Status
===========

The *Work Status* concept is used to define the different stages that a
project's `Work <model-project.work>` goes through.

Each status can be used with one, or more, types of work.

The progress set on the work status defines the minimum amount of progress
needed for work to have that status.

.. seealso::

   The available *Work Statuses* are found using the main menu item:

      |Projects --> Configuration --> Work Status|__

      .. |Projects --> Configuration --> Work Status| replace:: :menuselection:`Projects --> Configuration --> Work Status`
      __ https://demo.tryton.org/model/project.work
