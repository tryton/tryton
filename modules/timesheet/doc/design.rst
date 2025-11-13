******
Design
******

The *Timesheet Module* introduces or extends the following concepts:

.. _model-timesheet.work:

Timesheet Work
==============

A *Timesheet Work* represents a task, project, or any activity for which time
can be recorded.

Each work can be linked to another record via the :guilabel:`Origin` field,
allowing it to be used for time recording.
When a work has an origin, its name is automatically derived from it.

A Work may have start and end dates that restrict the period during which time
can be recorded.

The total time spent on each work is automatically calculated by summing all
related `Timesheet Lines <model-timesheet.line>`.
This calculation can be filtered by a date range and `employees
<company:model-company.employee>`.

.. seealso::

   The list of *Works* can be found by opening the main menu item:

      |Timesheet --> Configuration --> Works|__

      .. |Timesheet --> Configuration --> Works| replace:: :menuselection:`Timesheet --> Configuration --> Works`
      __ https://demo.tryton.org/model/timesheet.work

.. _model-timesheet.line:

Timesheet Line
==============

A *Timesheet Line* stores the duration of the time spent by an `employee
<company:model-company.employee>` on a specific `Work <model-timesheet.work>`
for a given date .

.. seealso::

   The list of *Lines* can be found by opening the main menu item:

      |Timesheet --> Lines|__

      .. |Timesheet --> Lines| replace:: :menuselection:`Timesheet --> Lines`
      __ https://demo.tryton.org/model/timesheet.line

Wizards
-------

.. _wizard-timesheet.line.enter:

Enter Timesheet Lines
^^^^^^^^^^^^^^^^^^^^^

The *Enter Timesheet Lines* wizard helps to quickly record time spent by an
`employee <company:model-company.employee>` on a given day by opening an
editable list of timesheet lines with the employee and date already filled in.

.. seealso::

   The *Enter Timesheet Lines*  wizard can be accessed from the main menu:

      |Timesheet --> Enter Lines|__

      .. |Timesheet --> Enter Lines| replace:: :menuselection:`Timesheet --> Enter Lines`
      __ https://demo.tryton.org/wizard/timesheet.line.enter
