===================
Attendance Scenario
===================

Imports::

    >>> import datetime as dt
    >>> from dateutil.relativedelta import relativedelta
    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> now = dt.datetime.now()
    >>> tomorrow = now + relativedelta(days=1)
    >>> next_week = now + relativedelta(days=7)

Activate attendance.line module::

    >>> config = activate_modules('attendance')

Create a company::

    >>> _ = create_company()
    >>> company = get_company()

Create an employee::

    >>> Party = Model.get('party.party')
    >>> Employee = Model.get('company.employee')
    >>> employee = Employee()
    >>> party = Party(name='Employee')
    >>> party.save()
    >>> employee.party = party
    >>> employee.company = company
    >>> employee.save()

Create an attendance record for the employee::

    >>> Attendance = Model.get('attendance.line')
    >>> attendance = Attendance()
    >>> attendance.type
    'in'
    >>> attendance.employee = employee
    >>> attendance.at = now
    >>> attendance.save()

    >>> attendance.date == now.date()
    True

When creating a new attendance the type is automatically set::

    >>> attendance = Attendance()
    >>> attendance.employee = employee
    >>> attendance.at = now + relativedelta(hours=2)
    >>> attendance.type
    'out'
    >>> attendance.save()

Close the period::

    >>> Period = Model.get('attendance.period')
    >>> period = Period()
    >>> period.ends_at = now + relativedelta(hours=4)
    >>> period.click('close')
    >>> period.state
    'closed'

You can't create attendances in closed periods::

    >>> attendance = Attendance()
    >>> attendance.employee = employee
    >>> attendance.at = now
    >>> attendance.type = 'in'
    >>> attendance.save() # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    PeriodClosedError: ...

But it is possible in open periods::

    >>> attendance.at = tomorrow
    >>> attendance.save()

Update attendance date time, update its date::

    >>> attendance.at = next_week
    >>> attendance.save()

    >>> attendance.date == next_week.date()
    True
