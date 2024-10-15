******
Design
******

The *Attendance Module* introduces the following concepts:

.. _model-attendance.line:

Attendance
==========

*Attendance* records when an `Employee <company:model-company.employee>` enters
or leaves the `Company's <company:model-company.company>` premises.

.. seealso::

   The *Attendance* lines can be found by opening the main menu item:

   |Attendance --> Attendances|__

   .. |Attendance --> Attendances| replace:: :menuselection:`Attendance --> Attendances`
   __ https://demo.tryton.org/model/attendance.line

.. _model-attendance.period:

Attendance Period
=================

The *Attendance Period* is used to group together all the `Attendance
<model-attendance.line>` lines that have taken place up to a certain date and
that were after any previous *Attendance Period*.

When an *Attendance Period* is closed, it is no longer possible to create,
modify or delete attendance lines before its date.

.. seealso::

   The *Attendance Periods* can be found by opening the main menu item:

   |Attendance --> Configuration --> Periods|__

   .. |Attendance --> Configuration --> Periods| replace:: :menuselection:`Attendance --> Configuration --> Periods`
   __ https://demo.tryton.org/model/attendance.period

.. _model-attendance.sheet:

Attendance Sheet
================

The *Attendance Sheet* reports, for each `Employee
<company:model-company.employee>` and day, the total duration the employee was
at the `Company's <company:model-company.company>` premises.
It also contains a detailed list of each individual visit within that duration.

.. note::
   When the :doc:`Timesheet Module <timesheet:index>` is activated, the
   *Attendance Sheet* also displays the duration of the employee's timesheets
   for comparison.

.. seealso::

   The *Attendance Sheets* can be found by opening the main menu item:

   |Attendance --> Sheets|__

   .. |Attendance --> Sheets| replace:: :menuselection:`Attendance --> Sheets`
   __ https://demo.tryton.org/model/attendance.sheet
