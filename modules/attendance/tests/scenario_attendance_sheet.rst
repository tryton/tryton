=========================
Attendance Sheet Scenario
=========================

Imports::

    >>> import datetime as dt

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules

Activate attendance.line module::

    >>> config = activate_modules('attendance')

Create a company::

    >>> _ = create_company()
    >>> company = get_company()

Create employees::

    >>> Party = Model.get('party.party')
    >>> Employee = Model.get('company.employee')
    >>> employee1 = Employee()
    >>> party1 = Party(name='Employee 1')
    >>> party1.save()
    >>> employee1.party = party1
    >>> employee1.company = company
    >>> employee1.save()
    >>> employee2 = Employee()
    >>> party2 = Party(name='Employee 2')
    >>> party2.save()
    >>> employee2.party = party2
    >>> employee2.company = company
    >>> employee2.save()

Fill attendances::

    >>> Attendance = Model.get('attendance.line')
    >>> def present(employee, type, at):
    ...     attendance = Attendance(employee=employee, at=at)
    ...     attendance.type = type
    ...     attendance.save()

    >>> present(employee1, 'in', dt.datetime(2020, 4, 1, 9))
    >>> present(employee1, 'out', dt.datetime(2020, 4, 1, 12))
    >>> present(employee1, 'in', dt.datetime(2020, 4, 1, 13))
    >>> present(employee1, 'in', dt.datetime(2020, 4, 1, 15))
    >>> present(employee1, 'out', dt.datetime(2020, 4, 1, 18))

Check attendance sheet::

    >>> Sheet = Model.get('attendance.sheet')
    >>> sheet, = Sheet.find([])
    >>> sheet.duration
    datetime.timedelta(seconds=28800)
    >>> sheet.date
    datetime.date(2020, 4, 1)
    >>> len(sheet.lines)
    3
    >>> sum([l.duration for l in sheet.lines], dt.timedelta())
    datetime.timedelta(seconds=28800)

Fill attendance over 1 day::

    >>> present(employee1, 'in', dt.datetime(2020, 4, 2, 20))
    >>> present(employee1, 'out', dt.datetime(2020, 4, 3, 6))

Check attendance sheet::

    >>> sheet, = Sheet.find([('date', '=', dt.date(2020, 4, 2))])
    >>> sheet.duration
    datetime.timedelta(seconds=36000)

Add attendance for other employee::

    >>> present(employee2, 'in', dt.datetime(2020, 4, 1, 10))
    >>> present(employee2, 'out', dt.datetime(2020, 4, 1, 16))

Check attendance sheet::

    >>> sheet, = Sheet.find([('employee', '=', employee2.id)])
    >>> sheet.duration
    datetime.timedelta(seconds=21600)
