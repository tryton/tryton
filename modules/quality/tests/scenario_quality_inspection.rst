===========================
Quality Inspection Scenario
===========================

Imports::

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('quality', create_company)

    >>> Control = Model.get('quality.control')
    >>> Inspection = Model.get('quality.inspection')

Create control::

    >>> control = Control(name="Test")
    >>> point = control.points.new()
    >>> point.string = "Boolean"
    >>> point.type_ = 'boolean'
    >>> point = control.points.new()
    >>> point.string = "Float"
    >>> point.type_ = 'float'
    >>> point.tolerance_lower = 10
    >>> point.tolerance_upper = 20
    >>> control.save()

Create an inspection that passes::

    >>> inspection = Inspection()
    >>> inspection.control = control
    >>> inspection.points
    {'boolean': None, 'float': None}
    >>> inspection.points = {'boolean': True, 'float': 15}
    >>> inspection.click('process')
    >>> inspection.state
    'passed'

Create an inspection that fails::

    >>> inspection = Inspection()
    >>> inspection.control = control
    >>> inspection.points = {'boolean': False, 'float': 15}
    >>> inspection.click('process')
    >>> inspection.state
    'failed'

Create an inspection below the lower tolerance::

    >>> inspection = Inspection()
    >>> inspection.control = control
    >>> inspection.points = {'boolean': True, 'float': 5}
    >>> inspection.click('process')
    >>> inspection.state
    'failed'

Create an inspection above the upper tolerance::

    >>> inspection = Inspection()
    >>> inspection.control = control
    >>> inspection.points = {'boolean': True, 'float': 25}
    >>> inspection.click('process')
    >>> inspection.state
    'failed'

Create a partial inspection::

    >>> inspection = Inspection()
    >>> inspection.control = control
    >>> inspection.points = {'boolean': True}
    >>> inspection.click('process')
    Traceback (most recent call last):
        ...
    InspectionValidationError: ...

Pass a failed inspection::

    >>> inspection = Inspection()
    >>> inspection.control = control
    >>> inspection.points = {'boolean': False, 'float': 15}
    >>> inspection.click('process')
    >>> inspection.state
    'failed'
    >>> inspection.click('pass_')
    >>> inspection.state
    'passed'

Its not possible to delete a passed inspection::

    >>> inspection.delete()
    Traceback (most recent call last):
        ...
    AccessError: ...

Reset an inspection back to pending::

    >>> inspection.click('pending')
    >>> inspection.state
    'pending'

It is possible to delete pending inspections::

    >>> inspection.delete()
