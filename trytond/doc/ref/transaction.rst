.. _ref-transaction:
.. module:: trytond.transaction

Transaction
===========

.. exception:: TransactionError

   The base class for transaction error that need to retry the transaction.

.. method:: TransactionError.fix(extras)

   Update the extras argument of :meth:`~Transaction.start` to restart the
   transaction without the error.

.. class:: Transaction

   Represents a Tryton transaction that contains thread-local parameters of a
   database connection.
   The Transaction instances are `context manager`_ that commits or
   rollbacks the database transaction.
   In the event of an exception the transaction is rolled back, otherwise it is
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

.. attribute:: Transaction.trigger_records

.. attribute:: Transaction.check_warnings

    The set of warnings already checked.

.. attribute:: Transaction.timestamp

.. attribute:: Transaction.started_at

   The monotonic timestamp when the transaction started.

.. attribute:: Transaction.language

   The language code defines in the context.

.. attribute:: Transaction.counter

   Count the number of modification made in this transaction.

.. attribute:: Transaction.check_access

   If the access must be enforced.

.. attribute:: Transaction.active_records

   If the active test is enabled for :class:`~trytond.model.DeactivableMixin`.

.. staticmethod:: Transaction.monotonic_time

   Return a monotonic time used to populate :attr:`~Transaction.started_at`.

.. method:: Transaction.start(database_name, user[, readonly[, context[, close[, autocommit, \**extras]]]])

   Start a new transaction and return a `context manager`_.
   The non-readonly transaction will be committed when exiting the ``with``
   statement without exception.
   The other cases will be rollbacked.

.. method:: Transaction.stop([commit])

   Stop the transaction.
   If commit is ``True``, the transaction will be committed otherwise it will
   be rollbacked.
   The `context manager`_ returned by :meth:`~Transaction.start` should be used
   instead of calling this method.

.. method:: Transaction.set_context(context, \**kwargs)

   Update the transaction context and return a `context manager`_.
   The context is restored when exiting the ``with`` statement.

.. method:: Transaction.reset_context()

   Clear the transaction context and return a `context manager`_.
   The context is restored when exiting the ``with`` statement.

.. method:: Transaction.set_user(user[, set_context])

   Modify the user of the transaction and return a `context manager`_.
   ``set_context`` will put the previous user id in the context to simulate the
   record rules.
   The user will be restored when exiting the ``with`` statement.

.. method:: Transaction.lock_table(table)

   Raise a :exc:`TransactionError` to retry the transaction if the table has
   not been locked at the start.

.. method:: Transaction.set_current_transaction(transaction)

   Add a specific ``transaction`` on the top of the transaction stack.
   A transaction is commited or rollbacked only when its last reference is
   popped from the stack.

.. method:: Transaction.new_transaction([autocommit[, readonly, \**extras]])

   Create a new transaction with the same database, user and context as the
   original transaction and adds it to the stack of transactions.

.. method:: Transaction.commit()

   Commit the transaction and all data managers associated.

.. method:: Transaction.rollback()

   Rollback the transaction and all data managers associated.

.. method:: Transaction.join(datamanager)

   Register in the transaction a data manager conforming to the `Two-Phase
   Commit protocol`_.

   This method returns the registered datamanager.
   It could be a different yet equivalent (in term of python equality)
   datamanager than the one passed to the method.

.. method:: Transaction.atexit(func, \*args, \*\*kwargs)

   Register a function to be executed upon normal transaction termination.
   The function can not use the current transaction because it will be already
   committed or rollbacked.

.. function:: check_access([func])

   When called with a function, it decorates the function to be executed with
   check of access rights.
   Otherwise it returns a `context manager`_ that check access rights until
   exiting.

.. function:: without_check_access([func])

   When called with a function, it decorates the function to be executed
   without check of access rights.
   Otherwise it returns a `context manager`_ that disable check access rights
   until exiting.

.. function:: active_records([func])

   When called with a function, it decorates the function to be executed with
   active test enabled.
   Otherwise it returns a `context manager`_ that enable active test.

.. function:: inactive_records(func)

   When called with a function, it decorates the function to be executed with
   active test disabled.
   Otherwise it returns a `context manager`_ that disables active test.

.. _`context manager`: http://docs.python.org/reference/datamodel.html#context-managers
.. _`PEP-0249`: https://www.python.org/dev/peps/pep-0249/
.. _`Two-Phase Commit protocol`: https://en.wikipedia.org/wiki/Two-phase_commit_protocol
