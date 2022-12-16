.. _topics-task-queue:

==========
Task Queue
==========

Tryton provides a way to run asynchronously some tasks. You must activate the
worker in the `queue` section of the :ref:`configuration
<topics-configuration>` and :ref:`run the worker manager
<topics-start-server>` otherwise the tasks will be run at the end of the
transaction.

A task is the parameters that defines how to call a method from a
:class:`trytond.model.Model`. This include the
:attr:`trytond.transaction.Transaction.context`, the
:attr:`trytond.transaction.Transaction.user` and the arguments.
The first argument of the method must be an instance or a list of instances of
:class:`trytond.model.Model`. This other arguments must be JSON-ifiable.

A task is pushed into the `queue` by calling the desired method on the
:attr:`trytond.model.Model.__queue__`. This stores in the queue all the current
parameters of the call and it will be execute by a worker or at the end of the
transaction if no worker is configured.
The following :attr:`trytond.transaction.Transaction.context` keys are used as
parameters for the queue:

    - `queue_name`: The name of the queue. Default value is `default`.

    - `queue_scheduled_at`: A `datetime.timedelta` to add to current time to
      define when the task should be started. Default value is `None` which
      means directly.

    - `queue_expected_at`: A `datetime.timedelta` to add to current time to
      define when the task should be finished. Default value is `None` which
      means as soon as possible.

.. warning::

    There is no access right verification during the execution of the task.

Example:

.. highlight:: python

::

    from trytond.model import Model

    class MyModel(Model):
        "My Model"
        __name__ = 'my_model'

        @classmethod
        def launch(cls, records):
            for record in records:
                cls.__queue__.process(record, 42)

        def process(self, value):
            self.value = value
