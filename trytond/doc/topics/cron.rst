.. _topics-cron:

=================
Scheduled Actions
=================

Tryton provides a scheduler (aka cron) which can execute methods of
:ref:`models <topics-models>` periodically at set intervals.

The planning is managed by ``ir.cron`` records which store the method to call
and the interval of time between calls. The method must be a class method of a
:class:`~trytond.model.Model` which can be called without any parameters.

To register a new method with the scheduler, you must extend the ``ir.cron``
model and append the new method to the
:attr:`~trytond.model.fields.Selection.selection` attribute of the ``method``
field in :meth:`~trytond.model.Model.__setup__()`. The name of the selection
must be the model name and the method name joined together with a ``|`` between
them.

Example:

.. highlight:: python

::

    from trytond.model import Model
    from trytond.pool import PoolMeta

    class Cron(metaclass=PoolMeta):
        __name__ = 'ir.cron'

        @classmethod
        def __setup__(cls):
            super().__setup__()
            cls.method.selection.append(
                ('my_model|my_method', "Run my method"),
                )


    class MyModel(Model):
        "My Model"
        __name__ = 'my_model'

        @classmethod
        def my_method(cls):
            pass
