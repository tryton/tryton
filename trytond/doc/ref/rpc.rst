.. _ref-rpc:
.. module:: trytond.rpc

RPC
===

.. class:: RPC([readonly[, instantiate[, [decorator, result[, check_access[, unique[, fresh_session[, cache[, timeout]]]]]]]]])

   Define the behavior of Remote Procedure Call.

Instance attributes are:

.. attribute:: RPC.readonly

   The transaction mode

.. attribute:: RPC.instantiate

   The position or the slice of the argument to be instanciated

.. attribute:: RPC.decorator

   The function to decorate the called procedure with

.. attribute:: RPC.result

   The function to transform the result

.. attribute:: RPC.check_access

   Set ``_check_access`` in the context to activate the access right on model
   and field.
   Default is ``True``.

.. attribute:: RPC.unique

   If set, it ensures the instantiated records are unique.
   Default is ``True``.

.. attribute:: RPC.fresh_session

   If set, it requires a fresh session.
   Default is ``False``.

.. attribute:: RPC.cache

   A :class:`RPCCache` instance to compute the cache duration for the answer.

.. attribute:: RPC.timeout

   The timeout in second for the call.
   ``0`` or ``None`` means no timeout is applied.
   Default is ``None``.


RPCCache
--------

.. class:: RPCCache([days[, seconds])

   Define cache duration of RPC result.

Instance attributes are:

.. attribute:: RPC.duration

   A :py:class:`datetime.timedelta` instance.

Instance methods are:

.. method:: RCP.headers

   Return a dictionary of the headers.

Exceptions
==========

.. exception:: RPCReturnException

   The base class of exceptions to return the result of ``result`` method
   instead of raising an exception.

   The :class:`~trytond.transaction.Transaction` is rollbacked and tasks are
   cleared.
