.. _ref-cache:
.. module:: trytond.cache

=====
Cache
=====

.. class:: Cache(name[, size_limit[, duration[, context]]])

The class is used to cache values between server requests. The `name` should be
unique and it's used to identify the cache. We usually use
`<class_name>.<content_name>` to make it unique. The `size_limit` parameter can
be used to limit the number of values cached and it has 1024 as the default
value.  The `duration` parameter defines how long a cached value stays valid
but if it is not set the value remains valid until it is cleared.  And the
`context` parameter is used to indicate if the cache depends on the user
context and is true by default.  The cache is cleaned on :class:`Transaction`
starts and resets on :class:`Transaction` commit or rollback.

.. warning::
    As there is no deepcopy of the values cached, they must never be mutated
    after being set in or retrieved from the cache.
..

.. method:: get(key[, default])

Retrieve the value of the key in the cache. If a `default` is specified it
will be returned when the key is missing otherwise it will return `None`.

.. method:: set(key, value)

Sets the `value` of the `key` in the cache.

.. method:: clear()

Clears all the keys in the cache.

.. classmethod:: sync(transaction)

Synchronize cache instances using transaction.

.. method:: sync_since(value)

Return `True` if the last synchronization was done before `value`.

.. classmethod:: commit(transaction)

Apply cache changes from transaction.

.. classmethod:: rollback(transaction)

Remove cache changes from transaction.

.. staticmethod:: drop(dbname)

Drops all the caches for database `dbname`

.. note::
    By default Tryton uses a MemoryCache, but this behaviour can be overridden
    by setting a fully qualified name of an alternative class defined in the
    configuration `class` of the `cache` section.
..
