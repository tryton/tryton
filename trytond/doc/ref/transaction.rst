.. _ref-transaction:
.. module:: trytond.transaction

===========
Transaction
===========

.. class:: Transaction

This class is a `singleton`_ that contains thread-local parameters of the
database transaction.

.. _`singleton`: http://en.wikipedia.org/wiki/Singleton_pattern


.. attribute:: Transaction.cursor

    The database cursor.

.. attribute:: Transaction.user

    The id of the user.

.. attribute:: Transaction.context

.. attribute:: Transaction.create_records

.. attribute:: Transaction.delete_records

.. attribute:: Transaction.delete

.. attribute:: Transaction.timestamp

.. attribute:: Transaction.language

    The language code defines in the context.

.. attribute:: Transaction.counter

    Count the number of modification made in this transaction.

.. method:: Transaction.start(database_name, user[, context])

    Start a new transaction and return a `context manager`_.

.. method:: Transaction.stop()

    Stop a started transaction. This method should not be called directly as it
    will be by the context manager when exiting the `with` statement.

.. method:: Transaction.set_context(context, \**kwargs)

    Update the transaction context and return a `context manager`_. The context
    will be restored when exiting the `with` statement.

.. method:: Transaction.set_user(user[, set_context])

    Modify the user of the transaction and return a `context manager`_.
    `set_context` will put the previous user id in the context to simulate the
    record rules. The user will be restored when exiting the `with` statement.

.. method:: Transaction.set_cursor(cursor)

    Modify the cursor of the transaction and return a `context manager`_. The
    previous cursor will be restored when exiting the `with` statement.

.. method:: Transaction.new_cursor()

    Change the cursor of the transaction with a new one on the same database
    and return a `context manager`_. The previous cursor will be restored when
    exiting the `with` statement and the new one will be closed.

.. _`context manager`: http://docs.python.org/reference/datamodel.html#context-managers
