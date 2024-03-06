.. _ref-pool:
.. module:: trytond.pool

Pool
====

.. class:: Pool([database_name])

   Store the instances of :class:`~trytond.model.Model`,
   :class:`~trytond.wizard.Wizard` and *Report* per database.

Static methods:

.. staticmethod:: Pool.register(klass, ..., type_, module[, depends])

   Register the classes of type (``model``, ``report`` or ``wizard``) for the
   module.

   If ``depends`` is set, the registration happens only if all the modules are
   activated.

.. staticmethod:: Pool.register_mixin(mixin, classinfo, module)

   Register the mixin for the module.

   The ``mixin`` are included to all subclasses of ``classinfo``.

Class methods:

.. classmethod:: Pool.start()

   Start the pool by registering all Tryton modules found.

.. classmethod:: Pool.stop(database_name)

   Stop the pool by removing instances for the database.

.. classmethod:: Pool.database_list()

   List all started databases.

.. classmethod:: Pool.refresh(database_name, modules)

   Stop the pool if it contains any of the modules.

Instance methods:

.. method:: Pool.get(name[, type])

   Return the named object of ``type`` from the pool.

.. method:: Pool.iterobject([type])

   Return an interator over objects of ``type``.

.. method:: Pool.fill(module, modules)

   Fill the pool with the registered classes from the module and for the
   activated modules and return a list of classes for each type in a
   dictionary.

.. method:: Pool.setup([classes])

   Call all setup methods of the classes provided or for all the registered
   classes.

.. method:: Pool.setup_mixin([type[, name]])

   Include all the mixin registered for the filled modules to the corresponding
   registered type of classes or named.


PoolMeta
--------

.. class:: PoolMeta

   A metaclass helper to setup __name__ on class to be registered in the
   :class:`Pool`.


PoolBase
--------

.. class:: PoolBase

   The base class of registered classes.

Class methods:

.. classmethod:: PoolBase.__setup__()

   Setup the class.

.. classmethod:: PoolBase.__post_setup__()

   Post setup the class.

.. classmethod:: PoolBase.__register__()

   Registare the class.
