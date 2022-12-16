.. _ref-rpc:
.. module:: trytond.rpc

===
RPC
===

.. class:: RPC([readonly[, instantiate[, result]]])

RPC is an object to define the behavior of Remote Procedur Call.

Instance attributes are:

.. attribute:: RPC.readonly

    The transaction mode

.. attribute:: RPC.instantiate

    The position of the argument to be instanciated

.. attribute:: RPC.result

    The function to transform the result
