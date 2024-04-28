# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime as dt
import random

from proteus import Model


def setup(config, activated, company, customers):
    Work = Model.get('project.work')

    customer_projects = {
            'Website': ['analysis', 'design', 'setup'],
            'Labels': ['design'],
            'Calendar': ['design'],
            }

    for name, task_names in customer_projects.items():
        project = Work(name=name, type='project', timesheet_available=False)
        project.party = random.choice(customers)
        for task_name in task_names:
            task = Work(name=task_name, type='task', timesheet_available=True)
            task.effort_duration = dt.timedelta(
                days=random.randint(10, 30),
                hours=random.randint(1, 5))
            task.progress = random.randint(1, 100) // 5 * 5 / 100.
            project.children.append(task)
        project.save()
