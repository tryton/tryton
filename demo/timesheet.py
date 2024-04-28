# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime as dt
import random

from dateutil.relativedelta import relativedelta

from proteus import Model


def setup(config, activated, company):
    Work = Model.get('timesheet.work')
    Employee = Model.get('company.employee')
    Line = Model.get('timesheet.line')

    for name in ['Marketing', 'Accounting', 'Secretary']:
        work = Work(name=name)
        work.save()

    employees = Employee.find([('company', '=', company.id)])
    works = Work.find([])

    today = dt.date.today()
    date = today + relativedelta(months=-1)
    day = dt.timedelta(hours=8)
    while date <= today:
        if date.weekday() < 5:
            for employee in employees:
                total = dt.timedelta()
                while total < day:
                    if random.random() > 0.8:
                        break
                    line = Line(employee=employee, date=date)
                    line.work = random.choice(works)
                    duration = dt.timedelta(hours=random.randint(1, 8))
                    line.duration = min(duration, day - total)
                    line.save()
        date += dt.timedelta(days=1)
