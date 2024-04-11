.. _ref-models:
.. module:: trytond.model

======
Models
======

.. contents::
   :local:
   :backlinks: entry
   :depth: 2

Model
=====

.. class:: Model([id[, \**kwargs]])

The base class that every kind of :ref:`model <topics-models>` inherits.

Class attributes are:

.. attribute:: Model.__name__

   The a unique name to reference the model throughout the platform.

.. attribute:: Model.__access__

   A set that contains the names of relation field for which the access rights
   are also checked for this model.

.. attribute:: Model.__rpc__

   A dictionary with method name as key and an instance of
   :class:`~trytond.rpc.RPC` as value.

.. attribute:: Model._rec_name

   The name of the field used as name of records.
   The default value is ``name``.

.. attribute:: Model.id

   The definition of the :class:`~trytond.model.fields.Integer` field ``id`` of
   records.

.. attribute:: Model.__queue__

   Return a queue caller for the model.
   The called method will be pushed into the queue.

.. attribute:: Model._fields

   A dictionary with the field name as key and its
   :class:`~fields.Field` instance as value.

.. attribute:: Model._record

   The record class to store internaly the values of the instances.

.. attribute:: Model._defaults

   A dictionary with the field name as key and its default method as value.

Class methods:

.. classmethod:: Model.__setup__()

   Setup the class before adding into the :class:`~trytond.pool.Pool`.
   See :meth:`trytond.pool.PoolBase.__setup__`.

.. classmethod:: Model.__post_setup__()

   Setup the class after added into the :class:`~trytond.pool.Pool`.
   See :meth:`trytond.pool.PoolBase.__post_setup__`.

.. classmethod:: Model.__register__(module_name)

   Register the model in ``ir.model`` and ``ir.model.field``.
   See :meth:`trytond.pool.PoolBase.__register__`.

.. classmethod:: Model.default_get(fields_names[, with_rec_name])

   Return a dictionary with the default values for each field in
   ``fields_names``.
   Default values are defined by the returned value of each instance method
   with the pattern ``default_<field name>()``.

   ``with_rec_name`` allow to add ``rec_name`` value for each many2one field.

   The ``default_rec_name`` key in the context can be used to define the value
   of the :attr:`~Model._rec_name` field.

   The ``default_<field name>`` keys in the context can be used to define the
   value of the field.

.. classmethod:: Model.fields_get([fields_names[, level]])

   Return the definition of each field on the model.

   ``level`` defines the number of relations to include in the relation field
   definition.

.. classmethod:: Model.__names__([field[, record]])

   Return a dictionary with the name of the ``model``, the ``field`` and the
   ``record`` and the ``value`` of the field.
   It is a convenience-method used to format messages which should include
   those names.

Instance methods:

.. method:: Model.pre_validate()

   Validate the instance before being stored.
   This method is called by the client to validate the instance.

ModelView
=========

.. class:: ModelView

Add the requirements to display the record in a view.

Class attributes:

.. attribute:: ModelView._buttons

   A dictionary with button name as key and the states dictionary for the
   button.
   The keys are ``invisible``, ``readonly`` and ``icon`` which have a
   :class:`~trytond.pyson.PYSON` statement as value and ``depends`` which has a
   list of field names on which the states depend.
   This is used as default attributes of the buttons for the views that show
   them.

Static methods:

.. staticmethod:: ModelView.button()

   Decorate button's method to check group access and rule.

.. staticmethod:: ModelView.button_action(action)

   Same as :meth:`~ModelView.button` but return the id of the XML id action or
   the action value updated by the returned value of the method.

.. staticmethod:: ModelView.button_change([\*fields[, methods]])

   Same as :meth:`~ModelView.button` but for button that change values of the
   fields on client side (similar to :ref:`on_change
   <topics-fields_on_change>`).

   ``methods`` can be used to duplicate the field names from other decorated
   methods.
   This is useful if the decorated method calls another method.

   .. note::
      Only on instance methods.

Class methods:

.. classmethod:: ModelView.fields_view_get([view_id[, view_type[, level]]])

   Return a view definition used by the client.
   The definition is::

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

   ``print``
      a list of available reports.
   ``action``
      a list of available actions.
   ``relate``
      a list of available relations.
   ``exports``
      a list of available exports.

.. classmethod:: ModelView.view_attributes()

   Returns a list of XPath, attribute, value and an optional depends list.
   Each element from the XPath will get the attribute set with the JSON encoded
   value.
   If the depends list is set its fields are added to the view if the xpath
   matches at least one element.

   .. note::

      The ``view_id`` is set to the
      :attr:`~trytond.transaction.Transaction.context` when this method is
      called.

.. classmethod:: ModelView.parse_view(tree, type[, view_id[, field_children[, level[, view_depends]]]])

   Return the sanitized XML and the corresponding fields definition.

   .. note::

      This method is public mainly to allow modification the existing XML of
      the view by code.

Instance methods:

.. method:: ModelView.on_change(fieldnames)

   Return the list of changes by calling ``on_change`` method of each field.

.. method:: ModelView.on_change_with(fieldnames)

   Return the new values of all fields by calling ``on_change_with`` method of
   each field.

.. method:: ModelView.on_change_notify(fieldnames)

    Returns a list of type and message couple to display on the client side.
    Available types are ``info``, ``warning`` and ``error``.

    .. note::
      To be called by the client, this method must be decorated
      by :meth:`~trytond.model.fields.depends` with the fields needed.

.. method:: ModelView.on_scan_code(code)

   Modify the instance when ``code`` is scanned.
   If the instance is not modified the scan loop ends.

   .. note::
      When extended, this method must be decorated by
      :meth:`~trytond.model.fields.depends` with the fields used.

.. method:: ModelView.autocomplete(text[, domain[, limit[, order]]])

   Return a list of dictionary for records completing ``text``.
   The dictionary is composed of ``id``, ``name`` and ``defaults``.

   The client call this method to provide completion.

   .. note::
      The ``defaults`` is used when ``id`` is empty to get the default values
      for the record to create.

ModelStorage
============

.. class:: ModelStorage

Add storage capability of record.

Class attributes are:

.. attribute:: ModelStorage.create_uid

   The definition of the :class:`~fields.Many2One` field that points to the
   user who created the record.

.. attribute:: ModelStorage.create_date

   The definition of the :class:`~fields.Timestamp` field that stores the
   creation time of the record.

.. attribute:: ModelStorage.write_uid

   The definition of the :class:`~fields.Many2One` field that points to the
   last user who modified the record.

.. attribute:: ModelStorage.write_date

   The definition of the :class:`~fields.Timestamp` field that stored the last
   modification time of the record.

.. attribute:: ModelStorage.rec_name

   The name of the :class:`~fields.Field` used as record name.

Static methods:

.. staticmethod:: ModelStorage.default_create_uid()

    Return the default value for :attr:`create_uid`.

.. staticmethod:: ModelStorage.default_create_date()

    Return the default value for :attr:`create_date`.

Class methods:

.. classmethod:: ModelStorage.log(records, event[, target[, user[, \**extra]]])

   Log event for records.

.. classmethod:: ModelStorage.create(vlist)

   Create records.

   ``vlist`` is list of dictionaries with fields names as key and created
   values as value and return the list of new instances.

.. classmethod:: ModelStorage.trigger_create(records)

   Trigger create actions.
   It calls actions defined in ``ir.trigger`` with ``on_create`` set and
   ``condition`` is true.

.. classmethod:: ModelStorage.read(ids, fields_names)

   Return a list of dictionary for the record ids.
   The dictionary is composed of the fields as key and their values.

   ``fields_names`` can contain dereferenced fields from related models.
   Their values will be returned under the referencing field suffixed by a
   ``.``.
   The number of *dots* in the name is not limited.
   The number of records read using *dots* can be limited with the
   ``related_read_limit`` key in the context.
   The remaining records will only contain the ``id`` field.

   ``fields_names`` can also contain ``<field>:string`` for
   :class:`~fields.Selection` or :class:`~fields.MultiSelection` fields.
   Their human-readable value are returned.

   The virtual fields ``_write`` and ``_delete`` can be used the read the
   writeable and deleteable state of the records.
   Regarding the ``_timestamp`` virtual fields it contains a timestamp that is
   used in the context to make a soft lock preventing update collisions.

   .. note::
      The order of the returned list is not guaranteed.

.. classmethod:: ModelStorage.index_get_field(name)

   Return the index to order of the calls to field get.

.. classmethod:: ModelStorage.write(records, values, [[records, values], ...])

   Write ``values`` on the list of records.

   ``values`` is a dictionary with fields names as key and writen values as
   value.

.. classmethod:: ModelStorage.trigger_write_get_eligibles(records)

   Return eligible records for write actions by triggers.
   This dictionary is to pass to :meth:`~ModelStorage.trigger_write`.

.. classmethod:: ModelStorage.trigger_write(eligibles)

   Trigger write actions.
   It will call actions defined in ``ir.trigger`` with ``on_write`` set and
   ``condition`` was false before :meth:`~ModelStorage.write` and true after.

.. classmethod:: ModelStorage.index_set_field(name)

   Return the index to order of the calls to field set.

.. classmethod:: ModelStorage.delete(records)

   Delete records.

.. classmethod:: ModelStorage.trigger_delete(records)

   Trigger delete actions.
   It will call actions defined in ``ir.trigger`` with ``on_delete`` set and
   ``condition`` is true.

.. classmethod:: ModelStorage.copy(records[, default])

   Duplicate the records.

   ``default`` is a dictionary of default value per field name for the created
   records.

   The values of ``default`` may be also callable that take a dictionary
   containing the fields and values of the record copied and return of the
   value.

   The keys of ``default`` may use the dotted notation for the
   :class:`~fields.One2Many` to define the default to pass to its ``copy``
   operation.

   New records are returned following the input order.

   .. note::

      The :class:`~fields.One2Many` and :class:`~fields.Many2Many` relation
      fields are not copied if their :attr:`~fields.Field.readonly` attribute
      is ``True`` or if their relationional :class:`Model` is not a
      :class:`ModelStorage` or if it has a :meth:`ModelSQL.table_query`.

.. classmethod:: ModelStorage.search(domain[, offset[, limit[, order[, count]]]])

   Return a list of records that match the :ref:`domain <topics-domain>`.

   If ``offset`` or ``limit`` are set, the result starts at the offset and has
   the length of the limit.

   The ``order`` is a list of tuples defining the order of the result::

      [ ('field name', 'ASC'), ('other field name', 'DESC'), ... ]

   The first element of the tuple is a field name of the model and the second
   is the sort ordering as ``ASC`` for ascending, ``DESC`` for descending or
   empty for a default order.
   This second element may contain ``NULLS FIRST`` or ``NULLS LAST`` to sort
   null values before or after non-null values.
   If neither is specified the default behavior of the backend is used.

   In case the field used is a :class:`~fields.Many2One`, it is also possible
   to use the dotted notation to sort on a specific field from the target
   record.
   Or for a :class:`~fields.Dict` field, the dotted notation is used to sort on
   the key's value.

   If ``count`` is set to ``True``, then the result is the number of records.
   The count result is limited upto the value of ``limit`` if set.

.. classmethod:: ModelStorage.search_count(domain[, offset[, limit]])

   Return the number of records that match the :ref:`domain <topics-domain>`.

   The result is limited upto the value of ``limit`` if set and reduced by offset.

.. classmethod:: ModelStorage.search_read(domain[, offset[, limit[, order[, fields_names]]]])

   Call :meth:`search` and :meth:`read` at once.

   Useful for the client to reduce the number of calls.

.. classmethod:: ModelStorage.search_rec_name(name, clause)

   :attr:`~fields.Function.searcher` for the :class:`~fields.Function` field
   :attr:`rec_name`.

.. classmethod:: ModelStorage.search_global(cls, text)

   Yield tuples (record, name, icon) for records matching text.

   It is used for the global search.

.. classmethod:: ModelStorage.estimated_count()

   Return an estimation of the number of records stored.

.. classmethod:: ModelStorage.browse(ids)

   Return a list of record instance for the ``ids``.

.. classmethod:: ModelStorage.export_data(records, fields_names[, header])

   Return a list of list of values for each ``records``.

   The list of values follows ``fields_names``.
   The result includes the description of the fields if ``header`` is set.

   Relational fields are defined with ``/`` at any depth.

   Descriptor on fields are available by appending ``.`` and the name of the
   method on the field that returns the descriptor.

.. classmethod:: ModelStorage.export_data_domain(domain, fields_names[, offset[, limit[, order[, header]]]])

   Call :meth:`search` and :meth:`export_data` together.

   Useful for the client to reduce the number of calls and the data transfered.

.. classmethod:: ModelStorage.import_data(fields_names, data)

   Create or update records for all values in ``data``.

   The field names of values must be defined in ``fields_names``.
   It returns the number of imported records.

.. classmethod:: ModelStorage.check_xml_record(records, values)

   Raise an :exc:`~trytond.model.exceptions.AccessError` if the records can not
   be modified because they originate from XML data.
   ``values`` is a dictionary of written values or ``None`` for deletion.

   It is used by :meth:`~ModelStorage.write` and :meth:`~ModelStorage.delete`
   to prevent modification of data coming from XML files.

   .. note::
      This method must be overiden to change this behavior.

.. classmethod:: ModelStorage.validate(records)

   Validate the integrity of records after creation and modification.

   This method must be overridden to add validation and must raise an
   :exc:`~trytond.model.exceptions.ValidationError` if validation fails.


.. classmethod:: ModelStorage.validate_fields(records, field_names)

   Validate the integrity of records after modification of the fields. This
   method must be overridden to add validation for the field names set and must
   raise an exception if validation fails.

Dual methods:

.. classmethod:: ModelStorage.save(records)

   Save the modification made on the records.

   .. warning::

      Fields that have a container as a value must be reassigned to the parent
      record in order to be saved when the parent record is saved.

Instance methods:

.. method:: ModelStorage.resources()

   Return a dictionary with the number of attachments (``attachment_count``),
   notes (``note_count``) and unread note (``note_unread``).

.. method:: ModelStorage.get_rec_name(name)

   :attr:`~fields.Function.getter` for the :class:`~fields.Function` field
   :attr:`rec_name`.

ModelSQL
========

.. class:: ModelSQL

Implement :class:`ModelStorage` for an SQL database.

Class attributes are:

.. attribute:: ModelSQL._table

   The name of the database table which is mapped to the class.

   If not set, the value of :attr:`~Model.__name__` is used with dots converted
   to underscores.

.. attribute:: ModelSQL._order

   The default ``order`` parameter of :meth:`~ModelStorage.search` method.

.. attribute:: ModelSQL._order_name

   The name of the field on which the records must be sorted when sorting on a
   field refering to the model.

   If not set, :attr:`~Model._rec_name` is used.

.. attribute:: ModelSQL._history

   If true, all changes on records are stored in an history table.

.. attribute:: ModelSQL._sql_constraints

   A list of SQL constraints that are added on the table::

      [ (<constraint name>, <constraint>, <xml id>), ... ]

   constraint name
      The name of the SQL constraint in the database.

   constraint
      An instance of :class:`Constraint`

   xml id
      The message id for :meth:`~trytond.i18n.gettext`

.. attribute:: ModelSQL._sql_indexes

   A :py:class:`set <set>` containing the :class:`Index` that are created on
   the table.

.. attribute:: ModelSQL._history_sql_indexes

   A :py:class:`set <set>` containing the :class:`Index` that are created on
   the history table.

Class methods:

.. classmethod:: ModelSQL.__table__()

   Return a SQL Table instance for the Model.

.. classmethod:: ModelSQL.__table_history__()

   Return a SQL Table instance for the history of Model.

.. classmethod:: ModelSQL.__table_handler__([module_name[, history]])

   Return a :class:`~trytond.backend.TableHandler` instance for the Model.

.. classmethod:: ModelSQL.table_query()

   Could be defined to use a custom SQL query instead of a table of the
   database.
   It should return a SQL FromItem.

   .. warning::
      By default all CRUD operation raises an error on models implementing this
      method so the :meth:`~ModelStorage.create`, :meth:`~ModelStorage.write`
      and :meth:`~ModelStorage.delete` methods may also been overriden if
      needed.

.. classmethod:: ModelSQL.history_revisions(ids)

   Return a sorted list of all revisions for ids.

   The list is composed of the date, id and username of the revision.

.. classmethod:: ModelSQL.restore_history(ids, datetime)

   Restore the record ids from history at the specified date time.

   Restoring a record still generates an entry in the history table.

   .. warning::
      No access rights are verified, the restored records are not validated and
      no triggers are called.

.. classmethod:: ModelSQL.restore_history_before(ids, datetime)

   Restore the record ids from history before the specified date time.

   Restoring a record still generates an entry in the history table.

   .. warning::
      No access rights are verified, the restored records are not validated and
      not triggers are called.

.. classmethod:: ModelSQL.search(domain[, offset[, limit[, order[, count[, query]]]]])

   Same as :meth:`ModelStorage.search` with the additional ``query`` argument.
   The ``domain`` is converted by :meth:`~ModelSQL.search_domain`.

   If ``query`` is set to ``True``, the the result is the SQL query.

.. classmethod:: ModelSQL.search_domain(domain[, active_test[, tables]])

   Convert a :ref:`domain <topics-domain>` into a SQL expression by returning
   the updated tables dictionary and a SQL expression.

   If ``active_test`` is set to ``False``, no clause against
   :attr:`DeactivableMixin.active` field is added to the domain.

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

.. classmethod:: ModelSQL.lock([records])

   Take a lock for update on the records or take a lock on the whole table.

Constraint
----------

.. class:: Constraint(table)

Represent a SQL constraint for the ``table``.

Instance attributes:

.. attribute:: Constraint.table

   The SQL Table on which the constraint is defined.

Check
^^^^^

.. class:: Check(table, expression)

Represent a check :class:`Constraint` which enforce the validity of the
``expression``.

Instance attributes:

.. attribute:: Check.expression

   The SQL expression to check.

Unique
^^^^^^

.. class:: Unique(table, \*columns)

Represent a unique :class:`Constraint` which enforce the uniqueness of the
group of columns.

Instance attributes:

.. attribute:: Unique.columns

   The tuple of SQL Column instances.

.. attribute:: Unique.operators

   The tuple of ``Equal`` operators.

Exclude
^^^^^^^

.. class:: Exclude(table[, (expression, operator), ...[, where]])

Represent an exclude :class:`Constraint` which guarantees that if any two rows
are compared on the specified expression using the specified operator not all
of these comparisons will return ``TRUE``.

Instance attributes:

.. attribute:: Exclude.excludes

   The tuple of expression and operator.

.. attribute:: Exclude.columns

   The tuple of expressions.

.. attribute:: Exclude.operators

   The tuple of operators.

.. attribute:: Exclude.where

   The clause for which the exclusion applies.

Index
-----

.. class:: Index(table[, \*expressions, [, \*\*options]])

Represent a SQL index for the ``table`` for the sequence of ``expressions``.
An ``expression`` is a :py:class:`tuple <tuple>` of SQL expression and a
:attr:`~Index.Usage`.

Available options are:

   * ``include``: a list of columns to include in the index
   * ``where``: the where clause for partial index

.. attribute:: Index.Unaccent(expression)

Apply unaccent function if the database supports it.

.. attribute:: Index.Usage(\*\*options)

Represent a usage of a SQL expression.
Available options are:

   * ``collation``: the name of the collation
   * ``order``: the sort order

.. attribute:: Index.Equality(\*\*options)

Represent an equality usage.

.. attribute:: Index.Range(\*\*options)

Represent an range usage.

.. attribute:: Index.Similarity(\*\*options)

Represent a similar usage only for text.
Additional options are available:

   * ``begin``: optimize for constant pattern and anchored to the beginning of
     the string


convert_from
------------

.. method:: convert_from(table, tables[, type_])

Return a SQL ``FromItem`` constructed by joining ``table`` and :ref:`tables
<ref-tables>` using ``type_`` with default value ``LEFT``.

Workflow
========

.. class:: Workflow

A mixin_ to handle transition check.

Class attribute:

.. attribute:: Workflow._transition_state

   The name of the field that will be used to check state transition.
   The default value is 'state'.

.. attribute:: Workflow._transitions

   A set containing tuples of from and to state.

Static methods:

.. staticmethod:: Workflow.transition(state)

   Decorate method to filter records for which the transition is valid and
   finally to update the state of the filtered record.

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

DictSchemaMixin
===============

.. class:: DictSchemaMixin

A mixin_ for the schema of :class:`~fields.Dict` field.

Class attributes are:

.. attribute:: DictSchemaMixin.name

   A :class:`~fields.Char` field for the name of the key.

.. attribute:: DictSchemaMixin.string

   A :class:`~fields.Char` field for the string of the key.

.. attribute:: DictSchemaMixin.help

   The :class:`~fields.Char` field used as the help text for the key.

.. attribute:: DictSchemaMixin.type\_

   The :class:`~fields.Selection` field for the type of the key.

   The available types are:

   * boolean
   * integer
   * char
   * float
   * numeric
   * date
   * datetime
   * selection

.. attribute:: DictSchemaMixin.digits

   The :class:`~fields.Integer` field for the digits number when the type is
   ``float`` or ``numeric``.

.. attribute:: DictSchemaMixin.domain

   A :ref:`domain <topics-domain>` constraint on the dictionary key that will
   be enforced only on the client side.

   The key must be referenced by its name in the left operator of the domain.
   The :ref:`PYSON <ref-pyson>` evaluation context used to compute the domain
   is the dictionary value.
   Likewise the domain is tested using the dictionary value.

.. attribute:: DictSchemaMixin.selection

   The :class:`~fields.Text` field to store the couple of key and label when
   the type is ``selection``.

   The format is a key/label separated by ":" per line.

.. attribute:: DictSchemaMixin.selection_sorted

   If the :attr:`selection` must be sorted on label by the client.

.. attribute:: DictSchemaMixin.selection_json

   The :class:`~fields.Function` field to return the JSON_ version of the
   :attr:`selection`.

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
   setting in the ``dict`` section of the configuration, the
   :attr:`Model.__name__` to ``False``.

Instance methods:

.. method:: DictSchemaMixin.get_selection_json(name)

   :attr:`~fields.Function.getter` for the :attr:`selection_json`.

.. method:: DictSchemaMixin.format(value[, lang])

   Format the value using the key definition and the language.

MatchMixin
==========

.. class:: MatchMixin

A mixin_ to add to a :class:`Model` a match method on pattern.
The pattern is a dictionary with field name as key and the value to compare.
The record matches the pattern if for all dictionary entries, the value of the
record is equal or not defined.

Instance methods:

.. method:: MatchMixin.match(pattern[, match_none])

   Return if the instance match the pattern.

   If ``match_none`` is set ``None`` value of the instance will be compared.

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

   Return a SQL expression that shards the column containing record id of model
   name.

.. classmethod:: UnionMixin.union_unshard(record_id)

   Return the original instance of the record for the sharded id.

.. classmethod:: UnionMixin.union_column(name, field, table, Model)

   Return the SQL column that corresponds to the field on the union model.

.. classmethod:: UnionMixin.union_columns(model)

   Return the SQL table and columns to use for the UNION for the model name.

SymbolMixin
===========

.. class:: SymbolMixin

A mixin_ to manage the display of symbols on the client side.

Instance methods:

.. method:: SymbolMixin.get_symbol(sign, [symbol])

   Return a symbol and its position.

   The position indicates whether the symbol should appear before (0) or after
   (1) the value.
   If no symbol parameter is supplied then the mixin uses the value of
   attribute named ``symbol``.

DigitsMixin
===========

.. class:: DigitsMixin

A mixin_ to manage the digits of :attr:`fields.Float.digits` and
:attr:`fields.Numeric.digits` from a :class:`Model`.

Instance methods:

.. method:: DigitsMixin.get_digits()

   Return a tuple of two integers to use a ``digits`` attribute.

sequence_ordered
================

.. function:: sequence_ordered([field_name, [field_label, [order]]])

Return a mixin_ class which defines the order of a :class:`ModelSQL` with an
:class:`~fields.Integer` field.

``field_name`` indicates the name of the field to be created and its default
values is ``sequence``.
``field_label`` defines the label which will be used by the field and defaults
to ``Sequence``.
Order specifies the order direction and defaults to ``ASC NULLS FIRST``.

sort
====

.. function:: sort(records, order)

Return a new list of records ordered by the ``order`` list defined like in
:meth:`~ModelStorage.search`.

MultiValueMixin
===============

.. class:: MultiValueMixin

A mixin_ for :class:`Model` to help having :class:`~fields.MultiValue` fields
with multi-values on a :class:`ValueMixin`.
The values are stored by creating one record per pattern.
The patterns are the same as those on :class:`MatchMixin`.

Class methods:

.. classmethod:: MultiValueMixin.multivalue_model(field)

   Return the :class:`ValueMixin` on which the values are stored for the field
   name.

   The default is class name suffixed by the field name.

.. classmethod:: MultiValueMixin.setter_multivalue(records, name, value, \*\*pattern)

   :attr:`~fields.Function.getter` method for the
   :class:`trytond.model.fields.Function` fields.

Instance methods:

.. method:: MultiValueMixin.multivalue_records(field)

   Return the list of all :class:`ValueMixin` records linked to the instance.

   By default, it returns the value of the first found
   :class:`~fields.One2Many` linked to the multivalue model or all the records
   of this one.

.. method:: MultiValueMixin.multivalue_record(field, \*\*pattern)

   Return a new record of :class:`ValueMixin` linked to the instance.

.. method:: MultiValueMixin.get_multivalue(name, \*\*pattern)

   Return the value of the field ``name`` for the pattern.

.. method:: MultiValueMixin.set_multivalue(name, value[, save], \*\*pattern)

   Store the value of the field ``name`` for the pattern.

   If ``save`` is true, it will be stored in the database, otherwise the
   modified :class:`ValueMixin` records are returned unsaved.
   ``save`` is true by default.

.. warning::
    To customize the pattern, both methods must be override the same way.

ValueMixin
==========

.. class:: ValueMixin

A mixin_ to store the values of :class:`MultiValueMixin`.

DeactivableMixin
================

.. class:: DeactivableMixin

A mixin_ to add soft deletion to the model.
It renders all the fields as read-only when the record is inactive.

Class attributes are:

.. attribute:: DeactivableMixin.active

   The definition of the :class:`trytond.model.fields.Boolean` field to store
   soft deletion state.

   False values is considered as soft deletion.

tree
====

.. function:: tree([parent[, name[, separator]]])

Return a mixin_ class :class:`TreeMixin`.

``parent`` indicates the name of the field that defines the parent of the tree
and its default value is ``parent``.
``name`` indicates the name of the field that defines the name of the record and
its default value is ``name``.
If ``separator`` is set, the :meth:`~ModelStorage.get_rec_name` constructs the
name by concatenating each parent names using it as separator and
:meth:`~ModelStorage.search_rec_name` is adapted to search across the tree.


.. class:: TreeMixin

.. classmethod:: TreeMixin.check_recursion(records)

   Helper method that checks if there is no recursion in the tree defined by
   :meth:`tree`.


.. function:: sum_tree(records, values[, parent])

   Helper method to sum ``values`` following up ``records`` tree using
   ``parent``.
   ``records`` must contain a complete branch of the tree.
   ``values`` is a dictionary with record id as key.

avatar_mixin
============

.. function:: avatar_mixin([size[, default]])

Return a mixin_ :class:`AvatarMixin`.

``size`` defines the size of the avatar image and its default value is ``64``.
``default`` indicates the name of the field to use for generating a default
avatar, if it's not set then no default avatar is generated.

.. class:: AvatarMixin

.. attribute::  AvatarMixin.avatars

   The :class:`~fields.One2Many` field used to store the ``ir.avatar`` records.

.. attribute:: AvatarMixin.avatar

   The :class:`~fields.Binary` field that contains the avatar.

.. attribute:: AvatarMixin.avatar_url

   The :class:`~fields.Char` field that containts the URL for the avatar.

.. attribute:: AvatarMixin.has_avatar

   Indicate whether the record has an avatar.

.. classmethod:: AvatarMixin.generate_avatar(records, field)

   Generate a default avatar for each record using the field.


.. _mixin: http://en.wikipedia.org/wiki/Mixin
.. _JSON: http://en.wikipedia.org/wiki/Json
.. _UNION: http://en.wikipedia.org/wiki/Union_(SQL)#UNION_operator


