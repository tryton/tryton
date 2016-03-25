.. _ref-transaction:
.. module:: trytond.transaction

===========
Transaction
===========

.. class:: Transaction

This class represents a Tryton transaction that contains thread-local
parameters of a database connection. The Transaction instances are 
`context manager`_ that will commit or rollback the database transaction. In
the event of an exception the transaction is rolled back, otherwise it is
commited.

.. attribute:: Transaction.database

    The database.

.. attribute:: Transaction.readonly

.. attribute:: Transaction.connection

    The database connection as defined by the `PEP-0249`_.

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

.. method:: Transaction.cursor()

    Returns a cursor object using the ``Transaction.connection``.

.. method:: Transaction.start(database_name, user[, readonly[, context[, close[, autocommit]]]])

    Start a new transaction and return a `context manager`_.

.. method:: Transaction.stop()

    Stop a started transaction and pop it from the stack of transactions.

    This method should not be called directly as it will be by the context
    manager when exiting the `with` statement.

.. method:: Transaction.set_context(context, \**kwargs)

    Update the transaction context and return a `context manager`_. The context
    will be restored when exiting the `with` statement.

.. method:: Transaction.set_user(user[, set_context])

    Modify the user of the transaction and return a `context manager`_.
    `set_context` will put the previous user id in the context to simulate the
    record rules. The user will be restored when exiting the `with` statement.

.. method:: Transaction.set_current_transaction(transaction)

    Add a specific ``transaction`` on the top of the transaction stack. A
    transaction is commited or rollbacked only when its last reference is
    popped from the stack.

.. method:: Transaction.new_transaction([autocommit[, readonly]])

    Create a new transaction with the same database, user and context as the
    original transaction and adds it to the stack of transactions.

.. method:: Transaction.join(datamanager)

    Register in the transaction a data manager conforming to the `Two-Phase
    Commit protocol`_. More information on how to implement such data manager
    is available at the `Zope documentation`_.

    This method returns the registered datamanager. It could be a different yet
    equivalent (in term of python equality) datamanager than the one passed to the
    method.

.. _`context manager`: http://docs.python.org/reference/datamodel.html#context-managers
.. _`PEP-0249`: https://www.python.org/dev/peps/pep-0249/
.. _`Two-Phase Commit protocol`: https://en.wikipedia.org/wiki/Two-phase_commit_protocol
.. _`Zope documentation`: http://zodb.readthedocs.org/en/latest/transactions.html#the-two-phase-commit-protocol-in-practice
