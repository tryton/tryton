.. _ref-backend:
.. module:: trytond.backend

=======
Backend
=======

The backend manages the database connection and schema manipulation.

.. contents::
   :local:
   :backlinks: entry
   :depth: 1

.. attribute:: name

   The name of the backend configured.

Database
========

.. class:: Database(name)

   Manage the connection to the named database.

.. method:: Database.connect()

   Connect to the database and return the instance.

.. method:: Database.get_connection([autocommit[, readonly]])

   Retrieve a connection object as defined by :pep:`249#connection`.
   If autocommit is set, the connection is committed after each statement.
   If readonly is set, the connection is read only.

.. method:: Database.put_connection(connection[, close])

   Release the connection.
   If close is set, the connection is discarded.

.. method:: Database.close()

   Close all connections.

.. classmethod:: Database.create(connection, database_name)

   Create the named database using the connection.

.. classmethod:: Database.drop(connection, database_name)

   Drop the named database using the connection.

.. method:: Database.list([hostname])

   Return a list of Tryton database names.
   ``hostname`` filters the databases with the same configured hostname.

.. method:: Database.init()

   Initialize the database schema.

.. method:: Database.test([hostname])

   Return if the database is a Tryton database.
   If ``hostname`` is set, it checks also if it has the same configured
   hostname.

.. method:: Database.nextid(connection, table[, count])

   Return the next ``count`` IDs for the ``table`` using the ``connection``.

   .. note:: It may return ``None`` for some database.

.. method:: Database.setnextid(connection, table, value)

   Set the ``value`` as current ID to the ``table`` using the ``connection``.

.. method:: Database.currid(connection, table)

   Return the current ID of the ``table`` using the ``connection``.

.. classmethod:: Database.lock(connection, table)

   Lock the ``table`` using the ``connection``.

.. method:: Database.lock_id(id[, timeout])

   Return the SQL expression to lock the ``id``.
   Set ``timeout`` to wait for the lock.

.. method:: Database.has_constraint(constraint)

   Return if the database handle the ``constraint``.

.. method:: Database.has_returning()

   Return if the database supports ``RETURNING`` in ``INSERT`` and ``UPDATE``.

.. method:: Database.has_multirow_insert()

   Return if the database supports ``INSERT`` of multi-rows.

.. method:: Database.has_select_for()

   Return if the database supports ``FOR UPDATE`` and ``FOR SHARE`` in
   ``SELECT``.

.. method:: Database.get_select_for_skip_locked()

   Return For class with skip locked.

.. method:: Database.has_window_functions()

   Return if the database supports window functions.

.. method:: Database.has_unaccent()

   Return if the database suppport unaccentuated function.

.. method:: Database.has_unaccent_indexable()

   Return if the database suppport unaccentuated function in index.

.. method:: Database.unaccent(value)

   Return the SQL expression of unaccentuated ``value``.

.. method:: Database.has_similarity()

   Return if the database suppports similarity function.

.. method:: Database.similarity(column, value)

   Return the SQL expression that compare the similarity of ``column`` and
   ``value``.

.. method:: Database.has_search_full_text()

   Return if the database suppports full text search.

.. method:: Database.format_full_text(\*documents[, language])

   Return the SQL expression that format the ``documents`` into text search
   vectors for the ``language``.

   The order of ``documents`` define the weight for proximity ranking.

.. method:: Database.format_full_text_query(query[, language])

   Convert the ``query`` expression into full text query.

.. method:: Database.search_full_text(document, query)

   Return the SQL expression for searching ``document`` with the ``query``.

.. method:: Database.rank_full_text(document, query[, normalize])

   Return the SQL expression to rank ``document`` with the ``query``.

.. classmethod:: Database.has_sequence()

   Return if the database supports sequence querying and assignation.

.. method:: Database.sequence_exist(connection, name)

   Return if the named sequence exists using the ``connection``.

.. method:: Database.sequence_create(connection, name[, number_increment[, start_value]])

   Create a named sequence incremented by ``number_increment`` or ``1`` and
   starting at ``start_value`` or ``1`` using the ``connection``.

.. method:: Database.sequence_update(connection, name[, number_increment[, start_value]])

   Modify the named sequence with ``number_increment`` and ``start_value``
   using the ``connection``.

.. method:: Database.sequence_rename(connection, old_name, new_name)

   Rename the sequece from ``old_name`` to ``new_name`` using the
   ``connection``.

.. method:: Database.sequence_delete(connection, name)

   Delete the named sequence using the ``connection``.

.. method:: Database.sequence_next_number(connection, name)

   Return the next number fo the named sequence using the ``connection``.

.. method:: Database.has_channel(connection, name)

   Return if the database supports ``LISTEN`` and ``NOTIFY`` on channel.

.. method:: Database.sql_type(type_)

   Return the namedtuple('SQLType', 'base type') corresponding to the SQL
   ``type_``.

.. method:: Database.sql_format(type_, value)

   Return the ``value`` casted for the SQL ``type_``.

.. method:: Database.json_get(column[, key])

   Return the JSON value of the JSON ``key`` from the ``column``.

.. method:: Database.json_key_exists(column, key)

   Return the SQL expression to test if ``key`` exists in the JSON ``column``.

.. method:: Database.json_any_keys_exist(column, keys)

   Return the SQL expression to test if any ``keys`` exist in the JSON
   ``column``.

.. method:: Database.json_all_keys_exist(column, keys)

   Return the SQL expression to test if all ``keys`` exist in the JSON
   ``column``.

.. method:: Database.json_contains(column, json)

   Rteurn the SQL expression to test if the JSON ``column`` contains ``json``.

TableHandler
============

.. class:: TableHandler(model[, history])

   Handle table for the ``model``.
   If ``history`` is set, the table is the one storing the history.

.. attribute:: TableHandler.namedatalen

   The maximing length of named data for the database.

.. attribute:: TableHandler.index_translators

   Contain the :class:`IndexTranslator` for the database.

.. classmethod:: TableHandler.table_exist(table_name)

   Return if the named table exists.

.. classmethod:: TableHandler.table_rename(old_name, new_name)

   Rename the table from ``old_name`` to ``new_name``.

.. method:: TableHandler.column_exist(column_name)

   Return if the named column exists.

.. method:: TableHandler.column_rename(old_name, new_name)

   Rename the column from ``old_name`` to ``new_name``.

.. method:: TableHandler.alter_size(column_name, column_type)

   Modify the size of the named column using the column type.

.. method:: TableHandler.alter_type(column_name, column_type)

   Modify the type of the named column.

.. method:: TableHandler.column_is_type(column_name, type_[, size])

   Return if the column is of type ``type_``.
   If ``type`` is ``VARCHAR``, ``size`` is also compared except if the value if
   negative.

.. method:: TableHandler.db_default(column_name, value)

   Set the default ``value`` on the named column.

.. method:: TableHandler.add_column(column_name, abstract_type[, default[, comment]])

   Add the named column of abstract type.
   The ``default`` is a method that return the value to fill the new column.
   ``comment`` set as comment for the column.

.. method:: TableHandler.add_fk(columns, reference[, ref_columns[, on_delete])

   Add a foreign key constraint on the named columns to target the
   ``ref_columns`` of ``reference`` table name.
   ``on_delete`` defines the method to use when foreign record is deleted.

.. method:: TableHandler.drop_fk(columns[, ref_columns[, table])

   Drop the foreign key constraint on the named columns targeting the
   ``ref_columns``.
   ``table`` can be used to alter another table.

.. method:: TableHandler.not_null_action(column_name[, action])

   Add or remove ``NOT NULL`` on the named column.

.. method:: TableHandler.add_constraint(ident, constraint)

   Add the SQL expression ``constraint`` as constraint named ``ident`` on the
   table.

.. method:: TableHandler.drop_constraint(ident[, table])

   Drop the named ``ident`` constraint.
   ``table`` can be used to alter another table.

.. method:: TableHandler.set_indexes(indexes[, concurrently])

   Create the :class:`indexes <trytond.model.Index>` if possible and drop
   others having ``idx_`` as prefix or ``_index`` as suffix.

   If ``concurrently`` is set indexes are created concurrently if possible.
   It defaults to ``False``.

.. method:: TableHandler.drop_column(column_name)

   Drop the named column.

.. classmethod:: TableHandler.drop_table(model, table[, cascade])

   Drop the named ``table`` and clean ``ir.model.data`` from the given
   ``model``.
   Set ``cascade`` to drop objects that depend on the table.

.. classmethod:: TableHandler.convert_name(name[, reserved])

   Convert the data name to be lower than namedatalen minus reserved.

.. method:: Database.index_translator_for(index)

   Return the best :class:`IndexTranslator` for the given index.

IndexTranslator
===============

.. class:: IndexTranslator

   Convert an :class:`~trytond.model.Index` into a concrete index.

.. classmethod:: IndexTranslator.definition(index)

   Return the name, SQL query and parameters to create the :class:`index
   <trytond.model.Index>`.

.. classmethod:: IndexTranslator.score(index)

   Return a score related to the fitness of using this translator for the
   :class:`index <trytond.model.Index>`.
   A score of ``0`` means that the translator is unsuited for the requested
   usage.

Exceptions
==========

.. exception:: DatabaseIntegrityError

   Exception raised when the relational integrity of the database is affected.

.. exception:: DatabaseDataError

   Exception raised for errors that are due to problems with the processed data.

.. exception:: DatabaseOperationalError

   Exception raised for errors that are related to the database’s operation.
