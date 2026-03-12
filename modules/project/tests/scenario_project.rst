================
Project Scenario
================

Imports::

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate project::

    >>> config = activate_modules('project', create_company)

    >>> Work = Model.get('project.work')

Create a project with a task::

    >>> project = Work(type='project', name="Project")
    >>> task = project.children.new(type='task', name="Task")
    >>> project.save()
    >>> task, = project.children

Check works have numbers::

    >>> bool(project.number)
    True
    >>> bool(task.number)
    True
