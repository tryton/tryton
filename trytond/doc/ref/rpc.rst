.. _ref-rpc:
.. module:: trytond.rpc

===
RPC
===

.. class:: RPC([readonly[, instantiate[, result[, check_access[, unique[, fresh_session[, cache]]]]]]])

RPC is an object to define the behavior of Remote Procedure Call.

Instance attributes are:

.. attribute:: RPC.readonly

    The transaction mode

.. attribute:: RPC.instantiate

    The position or the slice of the argument to be instanciated

.. attribute:: RPC.result

    The function to transform the result

.. attribute:: RPC.check_access

    Set `_check_access` in the context to activate the access right on model
    and field. Default is `True`.

.. attribute:: RPC.unique

    If set, it ensures the instantiated records are unique. Default is `True`.

.. attribute:: RPC.fresh_session

    If set, it requires a fresh session. Default is `False`.

.. attribute:: RPC.cache

    A :class:`RPCCache` instance to compute the cache duration for the answer.

========
RPCCache
========

.. class:: RPCCache([days[, seconds])

Instance attributes are:

.. attribute:: RPC.duration

    A timdelta instance.

Instance methods are:

.. method:: RCP.headers

    Returns a dictionary of the headers.
