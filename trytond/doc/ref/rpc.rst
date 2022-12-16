.. _ref-rpc:
.. module:: trytond.rpc

===
RPC
===

.. class:: RPC([readonly[, instantiate[, result[, check_access]]]])

RPC is an object to define the behavior of Remote Procedur Call.

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
