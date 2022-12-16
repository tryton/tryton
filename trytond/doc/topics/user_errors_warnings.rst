.. _topics-user_errors_warnings:

========================
User Errors and Warnings
========================

When processing a request, you can stop the flow by raising an exception that
will be displayed to the user as an error message or a warning. They are
respectively :exc:`~trytond.exceptions.UserError` and
:exc:`~trytond.exceptions.UserWarning`.

User Errors
===========

An error displays a message and optionally a description to the user.

Example:

.. highlight:: python

::

    from trytond.exceptions import UserError
    from trytond.model import Model

    class MyModel(Model):
        "My Model"
        __name__ = 'my_model'

        def process(self):
            if check_failed:
                raise UserError("You cannot process.", "because…")

.. note::
    They are often used in combination with :meth:`~trytond.i18n.gettext` to
    translate the messages.

User Warnings
=============

A warning displays a confirmation message with optionally a description to the
user. The user can decide to continue so the request is processed again without
stopping at the warning. Otherwise the user can cancel its request.
The warning instance is identified by a name which allows to skip it the next
time it is checked, that's why they often build using the ``format`` method
which uses record instances to generate a unique name based on ids.

Example:

.. highlight:: python

::

    from trytond.exceptions import UserWarning
    from trytond.model import Model
    from trytond.pool import Pool

    class MyModel(Model):
        "My Model"
        __name__ = 'my_model'

        def process(self):
            pool = Pool()
            Warning = pool.get('res.user.warning')
            warning_name = Warning.format('mywarning', [self])
            if Warning.check(warning_name):
                raise UserWarning(warning_name, "Process cannot be canceled.")

.. note::
    If there is no user interaction the warnings can be skipped by setting the
    ``_skip_warnings`` key of the context to ``True``.
