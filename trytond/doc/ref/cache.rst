.. _ref-cache:
.. module:: trytond.cache

Cache
=====

.. class:: Cache(name[, size_limit[, duration[, context]]])

   Use to cache values between server requests.

   The ``name`` should be unique and it's used to identify the cache.
   Usually ``<class_name>.<content_name>`` is used to make it unique.

   The ``size_limit`` parameter can be used to limit the number of values
   cached and it has ``1024`` as the default value.

   The ``duration`` parameter defines how long a cached value stays valid but
   if it is not set the value remains valid until it is cleared.

   And the ``context`` parameter is used to indicate if the cache depends on
   the user context and is ``True`` by default.

   The cache is cleaned on :class:`~trytond.transaction.Transaction` starts and
   resets on :class:`~trytond.transaction.Transaction` commit or rollback.

   .. warning::

       As there is no deepcopy of the values cached, they must never be mutated
       after being set in or retrieved from the cache.

.. attribute:: Cache.hit

   Count the number of times the cache returned a cached value.

.. attribute:: Cache.miss

   Count the number of times the cache did not contain the key.

.. classmethod:: Cache.stats()

   Yield statistics for each instance.

.. method:: Cache.get(key[, default])

   Retrieve the value of the key in the cache.

   If a ``default`` is specified it is returned when the key is missing
   otherwise it returns ``None``.

.. method:: Cache.set(key, value)

   Set the ``value`` of the ``key`` in the cache.

.. method:: Cache.clear()

   Clear all the keys in the cache.

.. classmethod:: Cache.clear_all()

   Clear all cache instances.

.. classmethod:: Cache.sync(transaction)

   Synchronize caches between servers using :class:`transaction
   <trytond.transaction.Transaction>` instance.

.. method:: Cache.sync_since(value)

   Return ``True`` if the last synchronization was done before ``value``.

.. classmethod:: Cache.commit(transaction)

   Apply cache changes from transaction.

.. classmethod:: Cache.rollback(transaction)

   Remove cache changes from transaction.

.. classmethod:: Cache.drop(dbname)

   Drop all caches for named database.

.. note::

    By default Tryton uses a MemoryCache, but this behaviour can be overridden
    by setting a fully qualified name of an alternative class defined in the
    :ref:`configuration <topics-configuration>` ``class`` of the ``cache``
    section.
