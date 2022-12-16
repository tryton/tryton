.. _ref-models:
.. module:: trytond.model

=====
Model
=====

.. class:: Model

This is the base class that every kind of :ref:`model <topics-models>`
inherits. It defines common attributes of all models.

Class attributes are:

.. attribute:: Model._name

    It contains the a unique name to reference the model throughout the
    platform.

.. attribute:: Model._inherits

    It contains a dictionary with one or more :attr:`Model._name` as keys. For each
    key a :class:`~trytond.model.fields.Many2One` field is defined as value. The
    :class:`trytond.model.fields.Many2One` fields must be defined in the the current
    model fields. A referenced model with ``_inherits`` is a generalization_ of the
    current model which is *specialized*. In the specialized model it is possible to
    interact with all attributes and methods of the general model.

    .. _generalization: http://en.wikipedia.org/wiki/Class_diagram#Generalization

.. attribute:: Model._description

    It contains a description of the model.

.. attribute:: Model._rpc

    It contains a dictionary with method name as key and a boolean as value. If
    a method name is in the dictionary then it is allowed to call it remotely.
    If the value is ``True`` then the transaction will be committed.

.. attribute:: Model._error_messages

    It contains a dictionary mapping keywords to an error message. By way of
    example::

        _error_messages = {
            'recursive_categories': 'You can not create recursive categories!',
            'wrong_name': 'You can not use " / " in name field!'
        }

.. attribute:: Model._rec_name

    It contains the name of the field used as name of records. The default
    value is 'name'.

.. attribute:: Model.id

    The definition of the field ``id`` of records.

Instance methods:

.. method:: Model.init(cursor, module_name)

    Registers the model in ``ir.model`` and ``ir.model.field``.

.. method:: Model.raise_user_error(cursor, error[, error_args[, error_description[, error_description_args[, raise_exception[, context]]]]])

    Raises an exception that will be displayed as an error message in the
    client.  ``error`` is the key of the error message in ``_error_messages``
    and ``error_args`` is the arguments for the "%"-based substitution of the
    error message.  There is the same parameter for an additional description.
    The boolean ``raise_exception`` can be set to ``False`` to retrieve the
    error message strings.

.. method:: Model.raise_user_warning(cursor, user, warning_name, warning[, warning_args[, warning_description[, warning_description_args[, context]]]])

    Raises an exception that will be displayed as a warning message on the
    client, if the user has not yet bypassed it. ``warning_name`` is used to
    uniquely identify the warning. Others parameters are like in
    :meth:`Model.raise_user_error`.

    .. warning::
        It requires that the cursor will be commited as it stores state of the
        warning states by users.
    ..

.. method:: Model.default_get(cursor, user, fields_names[, context[, with_rec_name]])

    Return a dictionary with the default values for each field in
    ``fields_names``. Default values are defined by the returned value of each
    instance method with the pattern ``default_`field_name`(cursor, user,
    [context])``. ``with_rec_name`` allow to add `rec_name` value for each
    many2one field.

.. method:: Model.fields_get(cursor, user[, fields_names[, context]])

    Return the definition of each field on the model.

=========
ModelView
=========

.. class:: ModelView

It adds requirements to display a view of the model in the client.

Instance methods:

.. method:: ModelView.fields_view_get(cursor, user[, view_id[, view_type[, context[, toolbar[, hexmd5]]]]])

    Return a view definition used by the client. The definition is::

        {
            'model': model name,
            'arch': XML description,
            'fields': {
                field name: {
                    ...
                },
            },
            'toolbar': {
                'print': [
                    ...
                ],
                'action': [
                    ...
                ],
                'relate': [
                    ...
                ],
            },
            ''md5': {
            },
        }

.. method:: ModelView.view_header_get(cursor, user, value[, view_type[, context]])

    Return the window title used by the client for the specific view type.

============
ModelStorage
============

.. class:: ModelStorage

It adds storage capability.

Class attributes are:

.. attribute:: ModelStorage.create_uid

    The definition of the :class:`trytond.model.fields.Many2One` field
    :attr:`create_uid` of records. It contains the :attr:`id` of the user who
    creates the record.

.. attribute:: ModelStorage.create_date

    The definition of the :class:`trytond.model.fields.DateTime` field
    :attr:`create_date` of records.  It contains the datetime of the creation of
    the record.

.. attribute:: ModelStorage.write_uid

    The definition of the :class:`trytond.model.fields.Many2One` field
    :attr:`write_uid` of the records.
    It contains the :attr:`id` of the last user who writes on the record.

.. attribute:: ModelStorage.write_date

    The definition of the :class:`trytond.model.fields.DateTime` field
    :attr:`write_date` of the records. It contains the datetime of the last
    write on the record.

.. attribute:: ModelStorage.rec_name

    The definition of the :class:`trytond.model.fields.Function` field
    :attr:`rec_name`. It is used in the client to display the records with a
    single string.

.. attribute:: ModelStorage._constraints

    The list of constraints that each record must respect. The definition is:

        [ ('function name', 'error keyword'), ... ]

    where ``function name`` is the name of an instance method of the class
    which must return a boolean (``False`` when the constraint is violated) and
    ``error keyword`` is a key of
    :attr:`Model._error_messages`.

Instance methods:

.. method:: ModelStorage.default_create_uid(cursor, user[, context])

    Return the default value for :attr:`create_uid`.

.. method:: ModelStorage.default_create_date(cursor, user[, context])

    Return the default value for :attr:`create_date`.

.. method:: ModelStorage.create(cursor, user, values[, context])

    Create a record. ``values`` is a dictionary with fields names as key and
    created values as value.

.. method:: ModelStorage.read(cursor, user, ids[, fields_names[, context]])

    Return values for the ids. If ``fields_names`` is set, there will be only
    values for these fields otherwise it will be for all fields.
    If ``ids`` is a list of ids, the returned value will be a list of
    dictionaries.
    If ``ids`` is an integer, the returned value will be a dictionary.

.. method:: ModelStorage.write(cursor, user, ids, values[, context])

    Write ``values`` on records. ``ids`` can be a list of ids or an id.
    ``values`` is a dictionary with fields names as key and writen values as
    value.

.. method:: ModelStorage.delete(cursor, user, ids[, context])

    Delete records. ``ids`` can be a list of ids or an id.

.. method:: ModelStorage.copy(cursor, user, ids[, default[, context]])

    Duplicate the records. ``ids`` can be a list of ids or an id. ``default``
    is a dictionary of default value for the created records.

.. method:: ModelStorage.search(cursor, user, domain[, offset[, limit[, order[, context[, count]]]]])

    Return a list of ids that match the :ref:`domain <topics-domain>`.

.. method:: ModelStorage.search_count(cursor, user, domain[, context])

    Return the number of records that match the :ref:`domain <topics-domain>`.

.. method:: ModelStorage.search_read(cursor, user, domain[, offset[, limit[, order[, context[, fields_names]]]]])

    Call :meth:`search` and :meth:`read` at once.
    Useful for the client to reduce the number of calls.

.. method:: ModelStorage.get_rec_name(cursor, user, ids, name[, context])

    Getter for the :class:`trytond.model.fields.Function` field
    :attr:`rec_name`.

.. method:: ModelStorage.search_rec_name(cursor, user, name, clause[, context])

    Searcher for the :class:`trytond.model.fields.Function` field
    :attr:`rec_name`.

.. method:: ModelStorage.browse(cursor, user, ids[, context])

    Return a :class:`BrowseRecordList` or a :class:`BrowseRecord` for the ``ids``.

.. method:: ModelStorage.export_data(cursor, user, ids, fields_names[, context])

    Return a list of list of values for each ``ids``.
    The list of values follows ``fields_names``.
    Relational fields are defined with ``/`` at any depth.

.. method:: ModelStorage.import_data(cursor, user, fields_names, datas[, context])

    Create records for all values in ``datas``.
    The field names of values must be defined in ``fields_names``.
    It returns a tuple containing: the number of records imported, the last values
    if failed, the exception if failed and the warning if failed.

.. method:: ModelStorage.check_xml_record(cursor, user, ids, values[, context])

    Verify if the ids are originating from XML data. It is used to prevent
    modification of data coming from XML files. This method must be overiden to
    change this behavior.

.. method:: ModelStorage.check_recursion(cursor, user, ids[, parent])

    Helper method that checks if there is no recursion in the tree composed
    with ``parent`` as parent field name.

.. method:: ModelStorage.workflow_trigger_trigger(cursor, user, ids[, context])

    Trigger a trigger event on the :ref:`workflow <topics-workflow>` of
    records.

========
ModelSQL
========

.. class:: ModelSQL

It implements :class:`ModelStorage` for an SQL database.

Class attributes are:

.. attribute:: ModelSQL._table

    The name of the database table which is mapped to the class.
    If not set, the value of :attr:`Model._name` is used with dots converted to
    underscores.

.. attribute:: ModelSQL._order

    A list of tuples defining the default order of the records:

        [ ('field name', 'ASC'), ('other field name', 'DESC'), ... ]

    where the first element of the tuple is a field name of the model and the
    second is the sort ordering as `ASC` for ascending or `DESC` for
    descending.

.. attribute:: ModelSQL._order_name

    The name of the field (or an SQL statement) on which the records must be
    sorted when sorting on this model from an other model. If not set,
    :attr:`ModelStorage._rec_name` will be used.

.. attribute:: ModelSQL._history

    If true, all changes on records will be stored in a history table.

.. attribute:: ModelSQL._sql_constraints

    A list of SQL constraints that are added on the table:

        [ ('constraint name', 'SQL constraint', 'error message key'), ... ]

    - `constraint name` is the name of the SQL constraint in the database

    - `SQL constraint` is the actual SQL constraint

    - `error message key` is the key of
      :attr:`_sql_error_messages`

.. attribute:: ModelSQL._sql_error_messages

    Like :attr:`Model._error_messages` but for :attr:`_sql_constraints`

Instance methods:

.. method:: ModelSQL.default_sequence(cursor, user[, context])

    Return default value for sequence field if the model has one.

.. method:: ModelSQL.table_query([context])

    Could be overrided to use a custom SQL query instead of a table of the
    database. It should return a tuple containing SQL query and arguments.

.. method:: ModelSQL.search_domain(cursor, user, domain[, active_test[, context]])

    Convert a :ref:`domain <topics-domain>` into a tuple containing:

    - a SQL clause string

    - a list of arguments for the SQL clause

    - a list of tables used in the SQL clause

    - a list of arguments for the tables

=============
ModelWorkflow
=============

.. class:: ModelWorkflow

It adds workflow capability to :class:`ModelStorage`.

Instance methods:

.. method:: ModelWorkflow.workflow_trigger_create(cursor, user, ids[, context])

    Trigger create event on the :ref:`workflow <topics-workflow>` of records.

.. method:: ModelWorkflow.workflow_trigger_write(cursor, user, ids[, context])

    Trigger write event on the :ref:`workflow <topics-workflow>` of records.

.. method:: ModelWorkflow.workflow_trigger_validate(cursor, user, ids[, context])

    Trigger validate event on the :ref:`workflow <topics-workflow>` of records.

.. method:: ModelWorkflow.workflow_trigger_delete(cursor, user, ids[, context])

    Trigger delete event on the :ref:`workflow <topics-workflow>` of records.

==============
ModelSingleton
==============

.. class:: ModelSingleton

Modify :class:`ModelStorage` into a singleton_.
This means that there will be only one record of this model.
It is commonly used to store configuration value.

.. _singleton: http://en.wikipedia.org/wiki/Singleton_pattern

Instance methods:

.. method:: ModelSingleton.get_singleton_id(cursor, user[, context])

    Return the id of the unique record if there is one.
