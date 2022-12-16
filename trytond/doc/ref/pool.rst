.. _ref-pool:
.. module:: trytond.pool

====
Pool
====

.. class:: Pool([database_name])

The Pool store the instances of models, wizards and reports per database.

Static methods:

.. staticmethod:: Pool.register(klass[, type])

    Register a class of type (default: `model`).

Class methods:

.. classmethod:: Pool.start()

    Start the pool by registering all Tryton modules found.

.. classmethod:: Pool.stop(database_name)

    Stop the pool by removing instances for the database.

.. classmethod:: Pool.database_list()

    List all started database.

Instance methods:

.. method:: Pool.get(name[, type])

    Return the named instance of type from the pool.

.. method:: Pool.object_name_list([type])

    Return the list of instances names.

.. method:: Pool.iterobject([type])

    Return an interator over instances names.

.. method:: Pool.setup(module)

    Setup classes for module and return a list of classes for each type in a
    dictionary.

========
PoolMeta
========

.. class:: PoolMeta

The PoolMeta is a metaclass helper to setup __name__ on class to be registered
in the Pool.
