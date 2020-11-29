.. _ref-filestore:
.. module:: trytond.filestore

=========
FileStore
=========

.. class:: FileStore()

The class is used to store and retrieve files from the directory defined in the
configuration ``path`` of ``database`` section. It uses a two levels of
directory composed of the 2 chars of the file hash. It is an append only
storage.

.. method:: get(id[, prefix])

Retrieve the content of the file referred by the id in the prefixed directory.

.. method:: getmany(ids[, prefix])

Retrieve a list of contents for the sequence of ids.

.. method:: size(id[, prefix])

Return the size of the file referred by the id in the prefixed directory.

.. method:: sizemany(ids[, prefix])

Return a list of sizes for the sequence of ids.

.. method:: set(data[, prefix])

Store the data in the prefixed directory and return the identifiers.

.. method:: setmany(data[, prefix])

Store the sequence of data and return a list of identifiers.

.. note::
    The class can be overridden by setting a fully qualified name of a
    alternative class defined in the configuration ``class`` of the ``database``
    section.
..
