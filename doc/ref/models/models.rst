.. _ref-models:
.. module:: trytond.model

=====
Model
=====

.. class:: Model([id[, \**kwargs]])

This is the base class that every kind of :ref:`model <topics-models>`
inherits. It defines common attributes of all models.

Class attributes are:

.. attribute:: Model.__name__

    It contains the a unique name to reference the model throughout the
    platform.

.. attribute:: Model.__rpc__

    It contains a dictionary with method name as key and an instance of
    :class:`trytond.rpc.RPC` as value.

.. attribute:: Model._rec_name

    It contains the name of the field used as name of records. The default
    value is 'name'.

.. attribute:: Model.id

    The definition of the field ``id`` of records.

.. attribute:: Model.__queue__

    It returns a queue caller for the model. The called method will be pushed
    into the queue.

.. attribute:: Model._fields
    It contains a dictionary with the field name as key and its
    :class:`~trytond.model.field` instance as value.

.. attribute:: Model._record
    It stores the record class to store internaly the values of the instances.

.. attribute:: Model._defaults
    It contains a dictionary with the field name as key and its default method
    as value.

Class methods:

.. classmethod:: Model.__setup__()

    Setup the class before adding into the :class:`trytond.pool.Pool`.

.. classmethod:: Model.__post_setup__()

    Setup the class after added into the :class:`trytond.pool.Pool`.

.. classmethod:: Model.__register__(module_name)

    Registers the model in ``ir.model`` and ``ir.model.field``.

.. classmethod:: Model.default_get(fields_names[, with_rec_name])

    Returns a dictionary with the default values for each field in
    ``fields_names``. Default values are defined by the returned value of each
    instance method with the pattern ``default_`field_name`()``.
    ``with_rec_name`` allow to add `rec_name` value for each many2one field.
    The `default_rec_name` key in the context can be used to define the value
    of the :attr:`Model._rec_name` field.

.. classmethod:: Model.fields_get([fields_names[, level]])

    Return the definition of each field on the model.
    The ``level`` defines the number of relations to include in the relation
    field definition.

.. classmethod:: Model.__names__([field])

    Returns a dictionary with the name of the `model` and the `field`.
    It is a convenience-method used to format messages which should include
    those names.

Instance methods:

.. method:: Model.on_change(fieldnames)

    Returns the list of changes by calling `on_change` method of each field.

.. method:: Model.on_change_with(fieldnames)

    Returns the new values of all fields by calling `on_change_with` method of
    each field.

.. method:: Model.pre_validate()

    This method is called by the client to validate the instance.

=========
ModelView
=========

.. class:: ModelView

It adds requirements to display a view of the model in the client.

Class attributes:

.. attribute:: ModelView._buttons

    It contains a dictionary with button name as key and the states dictionary
    for the button. This states dictionary will be used to generate the views
    containing the button.

Static methods:

.. staticmethod:: ModelView.button

    Decorate button method to check group access and rule.

.. staticmethod:: ModelView.button_action(action)

    Same as :meth:`ModelView.button` but return the action id of the XML `id`
    action or the action value updated by the returned value of the method.

.. staticmethod:: ModelView.button_change([\*fields])

    Same as :meth:`ModelView.button` but for button that change values of the
    fields on client side (similar to :ref:`on_change
    <ref-models-fields-on_change>`).

    .. warning::
        Only on instance methods.

Class methods:

.. classmethod:: ModelView.fields_view_get([view_id[, view_type[, level]]])

    Return a view definition used by the client. The definition is::

        {
            'model': model name,
            'type': view type,
            'view_id': view id,
            'arch': XML description,
            'fields': {
                field name: {
                    ...
                },
            },
            'field_childs': field for tree,
        }

.. classmethod:: ModelView.view_toolbar_get()

    Returns the model specific actions and exports in a dictionary with keys:
        - `print`: a list of available reports
        - `action`: a list of available actions
        - `relate`: a list of available relations
        - `exports`: a list of available exports

.. classmethod:: ModelView.view_attributes()

    Returns a list of XPath, attribute, value and an optional depends list.
    Each element from the XPath will get the attribute set with the JSON
    encoded value. If the depends list is set its fields are added to the
    view if the xpath matches at least one element.

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

Static methods:

.. staticmethod:: ModelStorage.default_create_uid()

    Return the default value for :attr:`create_uid`.

.. staticmethod:: ModelStorage.default_create_date()

    Return the default value for :attr:`create_date`.

Class methods:

.. classmethod:: ModelStorage.create(vlist)

    Create records. ``vlist`` is list of dictionaries with fields names as key
    and created values as value and return the list of new instances.

.. classmethod:: ModelStorage.trigger_create(records)

    Trigger create actions. It will call actions defined in ``ir.trigger`` if
    ``on_create`` is set and ``condition`` is true.

.. classmethod:: ModelStorage.read(ids, fields_names)

    Return a list of dictionary for the record ids. The dictionary is composed
    of the fields as key and their values.
    ``fields_names`` can contain dereferenced fields from related models.
    Their values will be returned under the referencing field suffixed by a
    `.`. The number of *dots* in the name is not limited.
    The order of the returned list is not guaranteed.

.. classmethod:: ModelStorage.write(records, values, [[records, values], ...])

    Write ``values`` on the list of records.  ``values`` is a dictionary with
    fields names as key and writen values as value.

.. classmethod:: ModelStorage.trigger_write_get_eligibles(records)

    Return eligible records for write actions by triggers. This dictionary
    is to pass to :meth:`~ModelStorage.trigger_write`.

.. classmethod:: ModelStorage.trigger_write(eligibles)

    Trigger write actions. It will call actions defined in ``ir.trigger`` if
    ``on_write`` is set and ``condition`` was false before
    :meth:`~ModelStorage.write` and true after.

.. classmethod:: ModelStorage.index_set_field(name)

    Return the index sort order of the field set calls.

.. classmethod:: ModelStorage.delete(records)

    Delete records.

.. classmethod:: ModelStorage.trigger_delete(records)

    Trigger delete actions. It will call actions defined in ``ir.trigger`` if
    ``on_delete`` is set and ``condition`` is true.

.. classmethod:: ModelStorage.copy(records[, default])

    Duplicate the records. ``default`` is a dictionary of default value per
    field name for the created records.

    The values of ``default`` may be also callable that take a dictionary
    containing the fields and values of the record copied and return of the
    value.

    The keys of ``default`` may use the dotted notation for the
    :class:`fields.One2Many` to define the default to pass to its `copy`
    operation.

    New records are returned following the input order.

.. classmethod:: ModelStorage.search(domain[, offset[, limit[, order[, count]]]])

    Return a list of records that match the :ref:`domain <topics-domain>`.

    If `offset` or `limit` are set, the result starts at the offset and has the
    length of the limit.

    The `order` is a list of tuples defining the order of the result:

            [ ('field name', 'ASC'), ('other field name', 'DESC'), ... ]

    The first element of the tuple is a field name of the model and the second
    is the sort ordering as `ASC` for ascending, `DESC` for descending or empty
    for a default order. This second element may contain 'NULLS FIRST' or
    'NULLS LAST' to sort null values before or after non-null values. If
    neither is specified the default behavior of the backend is used.

    In case the field used is a :class:`fields.Many2One`, it is also possible
    to use the dotted notation to sort on a specific field from the target
    record. Or for a :class:`fields.Dict` field, the dotted notation is used to
    sort on the key's value.

    If `count` is set to `True`, then the result is the number of records.

.. classmethod:: ModelStorage.search_count(domain)

    Return the number of records that match the :ref:`domain <topics-domain>`.

.. classmethod:: ModelStorage.search_read(domain[, offset[, limit[, order[, fields_names]]]])

    Call :meth:`search` and :meth:`read` at once.
    Useful for the client to reduce the number of calls.

.. classmethod:: ModelStorage.search_rec_name(name, clause)

    Searcher for the :class:`trytond.model.fields.Function` field
    :attr:`rec_name`.

.. classmethod:: ModelStorage.search_global(cls, text)

    Yield tuples (record, name, icon) for records matching text.
    It is used for the global search.

.. classmethod:: ModelStorage.browse(ids)

    Return a list of record instance for the ``ids``.

.. classmethod:: ModelStorage.export_data(records, fields_names)

    Return a list of list of values for each ``records``.
    The list of values follows ``fields_names``.
    Relational fields are defined with ``/`` at any depth.
    Descriptor on fields are available by appending ``.`` and the name of the
    method on the field that returns the descriptor.

.. classmethod:: ModelStorage.export_data_domain(domain, fields_names[, offset[, limit[, order]]])

    Call :meth:`search` and :meth`export_data` together.
    Useful for the client to reduce the number of calls and the data transfered.

.. classmethod:: ModelStorage.import_data(fields_names, data)

    Create or update records for all values in ``data``.
    The field names of values must be defined in ``fields_names``.
    It returns the number of imported records.

.. classmethod:: ModelStorage.check_xml_record(records, values)

    Verify if the records are originating from XML data. It is used to prevent
    modification of data coming from XML files. This method must be overiden to
    change this behavior.

.. classmethod:: ModelStorage.validate(records)

    Validate the integrity of records after creation and modification. This
    method must be overridden to add validation and must raise an exception if
    validation fails.

Dual methods:

.. classmethod:: ModelStorage.save(records)

    Save the modification made on the records.

Instance methods:

.. method:: ModelStorage.resources()

    Return a dictionary with the number of attachments (`attachment_count`),
    notes (`note_count`) and unread note (`note_unread`).

.. method:: ModelStorage.get_rec_name(name)

    Getter for the :class:`trytond.model.fields.Function` field
    :attr:`rec_name`.

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

    The default `order` parameter of :meth:`ModelStorage.search` method.

.. attribute:: ModelSQL._order_name

    The name of the field (or an SQL statement) on which the records must be
    sorted when sorting on a field refering to the model. If not set,
    :attr:`ModelStorage._rec_name` will be used.

.. attribute:: ModelSQL._history

    If true, all changes on records will be stored in a history table.

.. attribute:: ModelSQL._sql_constraints

    A list of SQL constraints that are added on the table:

        [ ('constraint name', constraint, 'xml id'), ... ]

    - `constraint name` is the name of the SQL constraint in the database

    - constraint is an instance of :class:`Constraint`

    - message id for :meth:`trytond.i18n.gettext`

Class methods:

.. classmethod:: ModelSQL.__table__()

    Return a SQL Table instance for the Model.

.. classmethod:: ModelSQL.__table_history__()

    Return a SQL Table instance for the history of Model.

.. classmethod:: ModelSQL.__table_handler__([module_name[, history]])

    Return a TableHandler for the Model.

.. classmethod:: ModelSQL.table_query()

    Could be defined to use a custom SQL query instead of a table of the
    database. It should return a SQL FromItem.

    .. warning::
        By default all CRUD operation will raise an error on models
        implementing this method so the create, write and delete methods may
        also been overriden if needed.
    ..

.. classmethod:: ModelSQL.history_revisions(ids)

    Return a sorted list of all revisions for ids. The list is composed of
    the date, id and username of the revision.

.. classmethod:: ModelSQL.restore_history(ids, datetime)

    Restore the record ids from history at the specified date time.
    Restoring a record will still generate an entry in the history table.

    .. warning::
        No access rights are verified and the records are not validated.
    ..

.. classmethod:: ModelSQL.restore_history_before(ids, datetime)

    Restore the record ids from history before the specified date time.
    Restoring a record will still generate an entry in the history table.

    .. warning::
        No access rights are verified and the records are not validated.
    ..

.. classmethod:: ModelSQL.search(domain[, offset[, limit[, order[, count[, query]]]]])

    Same as :meth:`ModelStorage.search` with the additional `query` argument.
    If `query` is set to `True`, the the result is the SQL query.

.. classmethod:: ModelSQL.search_domain(domain[, active_test[, tables]])

    Convert a :ref:`domain <topics-domain>` into a SQL expression by returning
    the updated tables dictionary and a SQL expression.

.. _ref-tables:

    Where ``tables`` is a nested dictionary containing the existing joins::

        {
            None: (<Table invoice>, None),
            'party': {
                None: (<Table party>, <join_on sql expression>),
                'addresses': {
                    None: (<Table address>, <join_on sql expression>),
                    },
                },
            }

Dual methods:

.. classmethod:: ModelSQL.lock(records)

    Take a lock for update on the records.

Constraint
==========

.. class:: Constraint(table)

It represents a SQL constraint on a table of the database and it follows the
API of the python-sql expression.

Instance attributes:

.. attribute:: Constraint.table

    The SQL Table on which the constraint is defined.

Check
-----

.. class:: Check(table, expression)

It represents a check :class:`Constraint` which enforce the validity of the
expression.

Instance attributes:

.. attribute:: Check.expression

    The SQL expression to check.

Unique
------

.. class:: Unique(table, \*columns)

It represents a unique :class:`Constraint` which enforce the uniqeness of the
group of columns with respect to all the rows in the table.

Instance attributes:

.. attribute:: Unique.columns

    The tuple of SQL Column instances.

.. attribute:: Unique.operators

    The tuple of `Equal` operators.

Exclude
-------

.. class:: Exclude(table[, (expression, operator), ...[, where]])

It represents an exclude :class:`Constraint` which guarantees that if any two
rows are compared on the specified expression using the specified operator not
all of these comparisons will return `TRUE`.

Instance attributes:

.. attribute:: Exclude.excludes

    The tuple of expression and operator.

.. attribute:: Exclude.columns

    The tuple of expressions.

.. attribute:: Exclude.operators

    The tuple of operators.

.. attribute:: Exclude.where

    The clause for which the exclusion applies.

========
Workflow
========

.. class:: Workflow

A Mix-in class to handle transition check.

Class attribute:

.. attribute:: Workflow._transition_state

    The name of the field that will be used to check state transition.

.. attribute:: Workflow._transitions

    A set containing tuples of from and to state.

Static methods:

.. staticmethod:: Workflow.transition(state)

    Decorate method to filter ids for which the transition is valid and finally
    to update the state of the filtered ids.

==============
ModelSingleton
==============

.. class:: ModelSingleton

Modify :class:`ModelStorage` into a singleton_.
This means that there will be only one record of this model.
It is commonly used to store configuration value.

.. _singleton: http://en.wikipedia.org/wiki/Singleton_pattern

Class methods:

.. classmethod:: ModelSingleton.get_singleton()

    Return the instance of the unique record if there is one.

===============
DictSchemaMixin
===============

.. class:: DictSchemaMixin

A mixin_ for the schema of :class:`trytond.model.fields.Dict` field.

Class attributes are:

.. attribute:: DictSchemaMixin.name

    The definition of the :class:`trytond.model.fields.Char` field for the name
    of the key.

.. attribute:: DictSchemaMixin.string

    The definition of the :class:`trytond.model.fields.Char` field for the
    string of the key.

.. attribute:: DictSchemaMixin.help

    The definition of the :class:`trytond.model.fields.Char` field used as the
    help text for the key.

.. attribute:: DictSchemaMixin.type\_

    The definition of the :class:`trytond.model.fields.Selection` field for the
    type of the key. The available types are:

    * boolean
    * integer
    * char
    * float
    * numeric
    * date
    * datetime
    * selection

.. attribute:: DictSchemaMixin.digits

    The definition of the :class:`trytond.model.fields.Integer` field for the
    digits number when the type is `float` or `numeric`.

.. attribute:: DictSchemaMixin.domain

   A :ref:`domain <topics-domain>` constraint on the dictionary key that will
   be enforced only on the client side.

   The key must be referenced by its name in the left operator of the domain.
   The :ref:`PYSON <ref-pyson>` evaluation context used to compute the domain
   is the dictionary value. Likewise the domain is tested using the dictionary
   value.

.. attribute:: DictSchemaMixin.selection

    The definition of the :class:`trytond.model.fields.Text` field to store the
    couple of key and label when the type is `selection`.
    The format is a key/label separated by ":" per line.

.. attribute:: DictSchemaMixin.selection_sorted

    If the :attr:`selection` must be sorted on label by the client.

.. attribute:: DictSchemaMixin.selection_json

    The definition of the :class:`trytond.model.fields.Function` field to
    return the JSON_ version of the :attr:`selection`.

Static methods:

.. staticmethod:: DictSchemaMixin.default_digits()

    Return the default value for :attr:`digits`.

Class methods:

.. classmethod:: DictSchemaMixin.get_keys(records)

    Return the definition of the keys for the records.

.. classmethod:: DictSchemaMixin.get_relation_fields()

   Return a dictionary with the field definition of all the keys like the
   result of :meth:`Model.fields_get`.

   It is possible to disable this method (returns an empty dictionary) by
   setting in the `dict` section of the configuration, the
   :attr:`Model.__name__` to ``False``.

Instance methods:

.. method:: DictSchemaMixin.get_selection_json(name)

    Getter for the :attr:`selection_json`.

==========
MatchMixin
==========

.. class:: MatchMixin

A mixin_ to add to a :class:`Model` a match method on pattern.
The pattern is a dictionary with field name as key and the value to compare.
The record matches the pattern if for all dictionary entries, the value of the
record is equal or not defined.

Instance methods:

.. method:: MatchMixin.match(pattern[, match_none])

    Return if the instance match the pattern. If `match_none` is set `None`
    value of the instance will be compared.

==========
UnionMixin
==========

.. class:: UnionMixin

A mixin_ to create a :class:`ModelSQL` which is the UNION_ of some
:class:`ModelSQL`'s. The ids of each models are sharded to be unique.

Static methods:

.. staticmethod:: UnionMixin.union_models()

    Return the list of :class:`ModelSQL`'s names

Class methods:

.. classmethod:: UnionMixin.union_shard(column, model)

    Return a SQL expression that shards the column containing record id of
    model name.

.. classmethod:: UnionMixin.union_unshard(record_id)

    Return the original instance of the record for the sharded id.

.. classmethod:: UnionMixin.union_column(name, field, table, Model)

    Return the SQL column that corresponds to the field on the union model.

.. classmethod:: UnionMixin.union_columns(model)

    Return the SQL table and columns to use for the UNION for the model name.

===========
SymbolMixin
===========

.. class:: SymbolMixin

A mixin_ to manage the display of symbols on the client side.

Instance methods:

.. method:: SymbolMixin.get_symbol(sign, [symbol])

    Return a symbol and its position.
    The position indicates whether the symbol should appear before (0) or after
    (1) the value. If no symbol parameter is supplied then the mixin uses the
    value of attribute named `symbol`.

================
sequence_ordered
================

.. method:: sequence_ordered([field_name, [field_label, [order]]])

Retuns a mixin_ class which defines the order of a :class:`ModelSQL` with an
:class:`trytond.model.fields.Integer` field. field_name indicates the name of
the field to be created and its default values is `sequence`. field_label
defines the label which will be used by the field and defaults to `Sequence`.
Order specifies the order direction and defaults to `ASC NULLS FIRST`.

===============
MultiValueMixin
===============

.. class:: MultiValueMixin

A mixin_ for :class:`Model` to help having
:class:`trytond.model.fields.MultiValue` fields with multi-values on a
:class:`ValueMixin`. The values are stored by creating one record per pattern.
The patterns are the same as those on :class:`MatchMixin`.

Class methods:

.. classmethod:: MultiValueMixin.multivalue_model(field)

    Return the :class:`ValueMixin` on which the values are stored for the
    field name. The default is class name suffixed by the field name.

.. classmethod:: MultiValueMixin.setter_multivalue(records, name, value, \*\*pattern)

    The setter method for the :class:`trytond.model.fields.Function` fields.

Instance methods:

.. method:: MultiValueMixin.multivalue_records(field)

    Return the list of all :class:`ValueMixin` records linked to the instance.
    By default, it returns the value of the first found
    :class:`trytond.model.fields.One2Many` linked to the multivalue model or
    all the records of this one.

.. method:: MultiValueMixin.multivalue_record(field, \*\*pattern)

    Return a new record of :class:`ValueMixin` linked to the instance.

.. method:: MultiValueMixin.get_multivalue(name, \*\*pattern)

    Return the value of the field `name` for the pattern.

.. method:: MultiValueMixin.set_multivalue(name, value[, save], \*\*pattern)

    Store the value of the field `name` for the pattern.
    If `save` is true, it will be stored in the database, otherwise the
    modified :class:`ValueMixin` records are returned unsaved. `save` is true
    by default.

.. warning::
    To customize the pattern, both methods must be override the same way.
..

==========
ValueMixin
==========

.. class:: ValueMixin

A mixin_ to store the values of :class:`MultiValueMixin`.

================
DeactivableMixin
================

.. class:: DeactivableMixin

A mixin_ to add soft deletion to the model. It renders all the fields as
read-only when the record is inactive.

Class attributes are:

.. attribute:: DictSchemaMixin.active

    The definition of the :class:`trytond.model.fields.Boolean` field to
    store soft deletion state. False values will be consideres as soft
    deletion.

.. _mixin: http://en.wikipedia.org/wiki/Mixin
.. _JSON: http://en.wikipedia.org/wiki/Json
.. _UNION: http://en.wikipedia.org/wiki/Union_(SQL)#UNION_operator

====
tree
====

.. method:: tree([parent[, name[, separator]]])

Returns a mixin_ class :class:`TreeMixin`. `parent` indicates the name of the
field that defines the parent of the tree and its default value is `parent`.
`name` indicates the name of the field that defines the name of the record and
its default value is `name`. If `separator` is set, the
:meth:`ModelStorage.get_rec_name` constructs the name by concatenating each
parent names using it as separator and :meth:`ModelStorage.search_rec_name` is
adapted to search across the tree.


.. class:: TreeMixin

.. classmethod:: TreeMixin.check_recursion(records)

    Helper method that checks if there is no recursion in the tree defined by
    :meth:`tree`.
