=============================
Attendance Timesheet Scenario
=============================

Imports::

    >>> import datetime as dt
    >>> from dateutil.relativedelta import relativedelta
    >>> from proteus import Model
    >>> from trytond import backend
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company

Activate attendance.line module::

    >>> config = activate_modules(['attendance', 'timesheet'])

Create a company::

    >>> _ = create_company()
    >>> company = get_company()

Create work::

    >>> Work = Model.get('timesheet.work')
    >>> work = Work(name="Work")
    >>> work.save()

Create an employee::

    >>> Party = Model.get('party.party')
    >>> Employee = Model.get('company.employee')
    >>> employee = Employee()
    >>> party = Party(name='Employee')
    >>> party.save()
    >>> employee.party = party
    >>> employee.company = company
    >>> employee.save()

Fill attendance::

    >>> Attendance = Model.get('attendance.line')
    >>> def present(employee, type, at):
    ...     attendance = Attendance(employee=employee, at=at)
    ...     attendance.type = type
    ...     attendance.save()

    >>> present(employee, 'in', dt.datetime(2020, 4, 1, 9))
    >>> present(employee, 'out', dt.datetime(2020, 4, 1, 12))
    >>> present(employee, 'in', dt.datetime(2020, 4, 1, 13))
    >>> present(employee, 'out', dt.datetime(2020, 4, 1, 18))

Fill time sheet::

    >>> Timesheet = Model.get('timesheet.line')
    >>> def spend(employee, work, date, duration):
    ...     timesheet = Timesheet(employee=employee, work=work)
    ...     timesheet.date = date
    ...     timesheet.duration =duration
    ...     timesheet.save()

    >>> spend(employee, work, dt.date(2020, 4, 1), dt.timedelta(hours=7))
    >>> spend(employee, work, dt.date(2020, 4, 2), dt.timedelta(hours=2))

Check attendance time sheet::

    >>> Sheet = Model.get('attendance.sheet')
    >>> sheet, = Sheet.find([('date', '=', dt.date(2020, 4, 1))])
    >>> sheet.duration == dt.timedelta(hours=8)
    True
    >>> sheet.timesheet_duration == dt.timedelta(hours=7)
    True

    >>> if backend.name != 'sqlite':
    ...     sheet, = Sheet.find([('date', '=', dt.date(2020, 4, 2))])
    ...     sheet.duration
    ...     sheet.timesheet_duration == dt.timedelta(hours=2)
    ... else:
    ...     True
    True
