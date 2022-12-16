.. _ref-cache:
.. module:: trytond.cache

=====
Cache
=====

.. class:: Cache(name[, size_limit[, context]])

The class is used to cache values between server requests. The `name` should
be unique and it's used to identify the cache. We usually use
`<class_name>.<content_name>` to make it unique. The `size_limit` field can
be used to limit the number of values cached and the `context` parameter
is used to indicate if the cache depends on the user context and is true
by default.
The cache is cleaned on :class:`Transaction` starts and resets on
:class:`Transaction` commit or rollback.

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

.. staticmethod:: clean(dbname)

Clean the cache for database `dbname`

.. staticmethod:: reset(dbname, name)

Reset the `name` cache for database `dbname`

.. staticmethod:: resets(dbname)

Resets all the caches stored for database `dbname`

.. staticmethod:: drop(dbname)

Drops all the caches for database `dbname`

.. note::
    By default Tryton uses a MemoryCache, but this behaviour can be overridden
    by setting a fully qualified name of an alternative class defined in the
    configuration `class` of the `cache` section.
..
