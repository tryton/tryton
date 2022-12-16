=======================
Project Status Scenario
=======================

Imports::

    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company

Activate project::

    >>> config = activate_modules('project')

Create a company::

    >>> _ = create_company()

Create status::

    >>> WorkStatus = Model.get('project.work.status')
    >>> in_progress = WorkStatus(name="In-Progress", types=['project'])
    >>> in_progress.progress = 0.1
    >>> in_progress.save()
    >>> open, = WorkStatus.find([('name', '=', "Open")])
    >>> done, = WorkStatus.find([('name', '=', "Done")])

Create a project with a task::

    >>> Work = Model.get('project.work')

    >>> project = Work(type='project', name="Project")
    >>> project.status == open
    True
    >>> task = project.children.new(name="Task")
    >>> task.status == open
    True

    >>> project.save()
    >>> task, = project.children

Open the project::

    >>> project.status = in_progress
    >>> project.progress
    0.1
    >>> project.save()

Try to complete project without task::

    >>> project.status = done
    >>> project.progress
    1.0
    >>> project.save()  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    WorkProgressValidationError: ...

    >>> task, = project.children
    >>> task.progress = 1
    >>> project.save()

Try to re-open task without project::

    >>> task = Work(task.id)
    >>> task.progress = 0.5
    >>> task.save()  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    WorkProgressValidationError: ...

Change progress with updating status::

    >>> project.progress = 0.8
    >>> project.save()  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    WorkProgressValidationError: ...

    >>> project.status = in_progress
    >>> project.save()

Re-open task::

    >>> task = Work(task.id)
    >>> task.progress = 0.5
    >>> task.save()

Copy the project::

    >>> project_copy, = project.duplicate()
    >>> project_copy.status == open
    True
    >>> project_copy.progress
