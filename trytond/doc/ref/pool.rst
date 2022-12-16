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

.. method:: Pool.iterobject([type])

    Return an interator over instances names.

.. method:: Pool.fill(module)

    Fill the pool with the registered class from the module and return a list
    of classes for each type in a dictionary.

.. method:: Pool.setup([classes])

    Call all setup methods of the classes provided or for all the registered
    classes.

========
PoolMeta
========

.. class:: PoolMeta

The PoolMeta is a metaclass helper to setup __name__ on class to be registered
in the Pool.

========
PoolBase
========

.. class:: PoolBase

The base class of registered class that will be setup.
