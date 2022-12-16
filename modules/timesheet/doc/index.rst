Timesheet Module
################

The timesheet module allow to track the time spent by employees on
various works. This module also comes with several reports that show
the time spent by employees on works following various time periods.


Work
****

A work is a generic concept that encompass all activities from simple
tasks to long-running projects. It can be alone or linked to another document.
The Work model contains the following fields:

- Name or Origin: The name or the origin of the work.
- Active: A checkbox that allow to disable the work.
- Company: The company for which the work is (or was) executed.


Timesheet Line
**************

A timesheet line expresses the fact that one employee spends part of
their time doing specific work on a given date. An optional
Description field allows extra information to be recorded about what
has been done.

.. toctree::
    :maxdepth: 1

    user_application
