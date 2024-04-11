.. _ref-models-fields:
.. module:: trytond.model.fields

======
Fields
======

.. contents::
   :local:
   :backlinks: entry
   :depth: 2

Field
=====

.. class:: Field

Fields define the behavior of the data on model's record.

The following attributes are available to all field types.
All are optional except :attr:`~Field.string`.

.. attribute:: Field.string

   A string for the label of the field.

.. attribute:: Field.help

   A multi-line help string for the field.

.. attribute:: Field.required

   If ``True``, the field is not allowed to be empty.
   Default is ``False``.

.. attribute:: Field.readonly

   If ``True``, the field is not editable in the client.
   Default is ``False``.

   .. warning::
      For relational fields, it means only the new, delete, add and remove
      buttons are inactivated.
      The editable state of the target record must be managed at the target
      model level.

.. attribute:: Field.domain

   A :ref:`domain <topics-domain>` constraint that is applied on the field
   value.

   The domain is enforced unless the field value is ``None``.

   .. note::

      For :class:`Reference` field it is a dictionary that contains the domain
      per model name.

.. attribute:: Field.states

   A dictionary that defines dynamic states of the field and overrides the
   static one.

   Possible keys are ``required``, ``readonly`` and ``invisible``.
   The values are :class:`~trytond.pyson.PYSON` statements that is evaluated
   with the values of the record.

.. attribute:: Field.on_change

   A set of field names.

   If this attribute is set, the client calls the method ``on_change_<field
   name>`` of the model when the user changes the current field value and will
   give the values of each fields in this list.

   The method signature is::

      on_change_<field name>()

   This method must change the value of the fields to be updated.

   .. note::

      The on_change_<field name> methods are running in a readonly transaction.

   The set of field names is filled by using the decorator :meth:`depends`.

.. attribute:: Field.on_change_with

   A set of field names.

   Same as :attr:`on_change`, but defined the other way around.
   If this attribute is set, the client will call the method
   ``on_change_with_<field name>`` of the model when the user changes one of
   the fields defined in the list and will give the values of each fields in
   this list.

   The method signature is::

      on_change_with_<field name>()

   This method must return the new value of the field.

   .. note::

      The on_change_with_<field name> methods are running in a readonly
      transaction.

   The set of field names is filled by using the decorator :meth:`depends`.

.. attribute:: Field.depends

   A :py:class:`set` of extra field names on which the field depends.

   This means that the client read also these fields even if they are not
   defined on the view.
   :attr:`Field.depends` is used for example to ensure that
   :class:`~trytond.pyson.PYSON` statement could be evaluated.

.. attribute:: Field.display_depends

   A computed set of field names on which the field depends when being
   displayed in a read only view.

.. attribute:: Field.edition_depends

   A computed set of field names on which the field depends when being
   displayed in a writable view.

.. attribute:: Field.validation_depends

   A computed set of field names on which the field depends when being
   validated.

.. attribute:: Field.context

   A dictionary which updates the current context for *relation field*.

   .. warning::

      The context could only depend on direct field of the record and without
      context.

.. attribute:: Field.loading

   Define how the field must be loaded: ``lazy`` or ``eager``.

.. attribute:: Field.name

   The name of the field.

Instance methods:

.. method:: Field.convert_domain(domain, tables, Model)

    Convert the simple :ref:`domain <topics-domain>` clause into a SQL
    expression or a new domain.
    :ref:`tables <ref-tables>` could be updated to add new joins.

.. method:: Field.sql_format(value)

    Convert the value to use as parameter of SQL queries.

.. method:: Field.sql_type()

    Return the namedtuple('SQLType', 'base type') which defines the SQL type to
    use for definition and casting.
    Or ``None`` if the field is not stored in the database.

    sql_type is using the ``_sql_type`` attribute to compute its return value.
    The backend is responsible for the computation.

    For the list of supported types by Tryton see :ref:`backend types
    <topics-backend_types>`.

.. method:: Field.sql_cast(expression)

    Return the SQL expression with cast with the type of the field.

.. method:: Field.sql_column(table)

    Return the Column instance based on table.

.. method:: Field.set_rpc(model)

    Add to :class:`model <trytond.model.Model>` the default
    :class:`~trytond.rpc.RPC` instances needed by the field.

.. method:: Field.definition(model, language)

    Return a dictionary with the definition of the field.

.. method:: Field.definition_translations(model, language)

    Return a list of translation sources used by :meth:`~Field.definition`.

.. method:: Field.searchable(model)

   Return True if the field is searchable.

.. method:: Field.sortable(model)

   Return True if the field is sortable.

Default value
=============

See :ref:`default value <topics-fields_default_value>`

Searching
=========

A class method could be defined for each field which must return a SQL
expression for the given domain instead of the default one.
The method signature is::

    domain_<field name>(domain, tables)

Where ``domain`` is the simple :ref:`domain <topics-domain>` clause and
``tables`` is a nested dictionary, see :ref:`tables <ref-tables>`.

Ordering
========

A class method could be defined for each field which must return a list of SQL
expression on which to order instead of the field.
The method signature is::

    order_<field name>(tables)

Where ``tables`` is a nested dictionary, see :ref:`tables <ref-tables>`.

Depends
=======

.. method:: depends([\*fields[, methods]])

   A decorator to define the field names on which the decorated method depends.

   The ``methods`` argument can be used to duplicate the field names from other
   decorated methods.
   This is useful if the decorated method calls another method.

.. _ref-models-fields-types:

Field types
===========

Boolean
-------

.. class:: Boolean(string[, \**options])

   A :py:class:`boolean <bool>` field.

Integer
-------

.. class:: Integer(string[, \**options])

   An :py:class:`integer <int>` field.

Char
----

.. class:: Char(string[, size[, translate[, strip[, \**options]]]])

   A single line :py:class:`string <str>` field.

   Search by similarity is used for the ``ilike`` operator and
   :meth:`~trytond.tools.is_full_text` value if the backend supports it and a
   threshold is set.
   The similarity threshold is defined for the context key ``<model
   name>.<field name>.search_similarity`` or ``search_similarity``.

   The field is ordered using the similarity with the context value from the
   key ``<model name>.<field name>.order`` if it is set.

:class:`Char` has some extra arguments:

.. attribute:: Char.size

   The maximum length (in characters) of the field. The size is enforced at the
   storage level and in the client input.
   The value can be a :class:`~trytond.pyson.PYSON` statement.

.. attribute:: Char.translate

   If ``True``, the value of the field is translatable.
   The value readed and stored will depend on the ``language`` defined in the
   context.

.. attribute:: Char.strip

   If ``True``, leading and trailing whitespace are removed.
   If ``leading``, leading whitespace are removed.
   If ``trailing``, trailing whitespace are removed.
   The default value is ``True``.

.. attribute:: Char.autocomplete

   A set of field names.

   If this attribute is set, the client calls the method ``autocomplete_<field
   name>`` of the :class:`model <trytond.model.Model>` when the user changes
   one of those field values.
   The method signature is::

      autocomplete_<field name>()

   This method must return a list of string that is used by the client to make
   autocompletion proposal.
   The set of field names could be filled by using the decorator :meth:`depends`.

.. attribute:: Char.search_unaccented

   If this attribute is set to ``True``, ``ilike`` searches is performed on
   unaccented strings.
   The default value is ``True``.

   .. warning::

      The database backend must supports unaccented search.

.. attribute:: Char.search_full_text

   If this attribute is set to ``True``, ``ilike`` searches with an
   :meth:`~trytond.tools.is_full_text` value use the full text search of the
   backend.
   The default value is ``False``.

   The context can be used to force the full text search behaviour.
   This is done using the key ``<model name>.<field name>.search_full_text``.
   If ``True``, the full text search is used no matter what the value.
   If ``False``, no full text search is peformed.

   The full text ranking value is added to the similarity if the
   ``search_full_text`` is ``True``.

   .. note::

      The database backend must support full text search otherwise ``ilike`` is
      always used.

Text
----

.. class:: Text(string[, size[, translatable[, \**options]]])

   A multi line :py:class:`string <str>` field.

:class:`Text` has some extra arguments:

.. attribute:: Text.size

   Same as :attr:`Char.size`.

.. attribute:: Text.translate

   Same as :attr:`Char.translate`.

.. attribute:: Text.search_unaccented

   Same as :attr:`Char.search_unaccented`.

.. attribute:: Text.search_full_text

   Same as :attr:`Char.search_full_text`.
   The default value is ``True``.

FullText
--------

.. class:: FullText(\**options)

   An internal field to store a list of parsed strings ordered by weights.
   The field is ordered using the full text ranking with the context value from
   the key ``<model name>.<field name>.order`` if it is set.


Float
-----

.. class:: Float(string[, digits[, \**options]])

   A :py:class:`floating-point number <float>` field.
   It is represented in Python by a ``float`` instance.

:class:`Float` has some extra arguments:

.. attribute:: Float.digits

   A tuple of two :py:class:`integers <int>`.

   The first integer defines the total of numbers in the integer part.

   The second integer defines the total of numbers in the decimal part.

   Integers can be replaced by a :class:`~trytond.pyson.PYSON` statement.
   If digits is ``None`` or any values of the tuple is ``None``, no validation
   on the numbers is done.
   The tuple can be replaced by a string containing the name of a
   :class:`Many2One` pointing to a :class:`~trytond.model.DigitsMixin`.

Numeric
-------

.. class:: Numeric(string[, digits[, \**options]])

   A :py:class:`fixed-point number <decimal.Decimal>` field.

:class:`Numeric` has some extra arguments:

.. attribute:: Numeric.digits

   Same as :attr:`Float.digits`.

Date
----

.. class:: Date(string[, \**options])

   A :py:class:`date <datetime.date>` field.

Instance methods:

.. method:: Date.sql_cast(expression[, timezone])

   Return the SQL expression cast as date.

   If timezone is set the expression is first converted to this timezone.

DateTime
--------

.. class:: DateTime(string[, format, \**options])

   A :py:class:`date and time <datetime.datetime>` field.

   It is stored in `UTC`_ while displayed in the user timezone.

.. _`UTC`: https://en.wikipedia.org/wiki/Coordinated_Universal_Time

:class:`DateTime` has some extra arguments:

.. attribute:: DateTime.format

   A string format as used by :py:meth:`~datetime.datetime.strftime`.

   This format is used to display the time part of the field.
   The default value is ``%H:%M:%S``.
   The value can be replaced by a :class:`~trytond.pyson.PYSON` statement.

Timestamp
---------

.. class:: Timestamp(string[, \**options])

   A :py:class:`timestamp <datetime.datetime>` field.

Time
----

.. class:: Time(string[, format, \**options])

   A :py:class:`time <datetime.time>` field.

:class:`Time` has some extra arguments:

.. attribute:: Time.format

    Same as :attr:`DateTime.format`.

TimeDelta
---------

.. class:: TimeDelta(string[, converter[, \**options]])

   An :py:class:`interval <datetime.timedelta>` field.

:class:`TimeDelta` has some extra arguments:

.. attribute:: TimeDelta.converter

   The name of the context key containing the time converter.

   A time converter is a dictionary with the keys:
   ``s`` (second), ``m`` (minute), ``h`` (hour), ``d`` (day), ``w`` (week),
   ``M`` (month), ``Y`` (year) and the value in second.

Binary
------

.. class:: Binary(string[, \**options])

   A :py:class:`binary <bytes>` field.

   .. warning::

      If the context contains a key composed of the model name and field name
      separated by a dot and its value is the string ``size`` then the read
      value is the size instead of the content.

:class:`Binary` has some extra arguments:

.. attribute:: Binary.filename

   Name of the field that holds the data's filename.

   Default value is an empty string, which means the data has no filename (in
   this case, the filename is hidden, and the "Open" button is hidden when the
   widget is set to "image").

.. attribute:: Binary.file_id

   Name of the field that holds the ``FileStore`` identifier.

   Default value is ``None`` which means the data is stored in the database.
   The field must be on the same table and accept ``char`` values.

   .. warning::

      Switching from database to file-store is supported transparently.
      But switching from file-store to database is not supported without
      manually upload to the database all the files.

.. attribute:: Binary.store_prefix

   The prefix to use with the ``FileStore``.

   Default value is ``None`` which means the database name is used.

Selection
---------

.. class:: Selection(selection, string[, sort[, selection_change_with[, translate[, help_selection[, \**options]]]]])

   A :py:class:`string <str>` field with limited values to choose from.

:class:`Selection` has some extra arguments:

.. attribute:: Selection.selection

   A list of 2-tuples that looks like this::

      [('M', 'Male'), ('F', 'Female')]

   The first element in each tuple is the actual value stored.
   The second element is the human-readable name.

   It can also be the name of a class or instance method on the model, that
   returns an appropriate list.
   The signature of the method is::

      selection()

   .. note::
      The method is automaticly added to :attr:`trytond.model.Model.__rpc__` if
      not manually set.

.. attribute:: Selection.sort

   If ``True``, the choices is sorted by human-readable value.

   Default value is ``True``.

   .. note::
      If it is ``False``, search results ordered by the field uses the index of
      the selection instead of the human-readable name.

.. attribute:: Selection.selection_change_with

   A set of field names.

   If this attribute is set, the client calls the ``selection`` method of
   the model when the user changes on of the fields defined in the list and
   gives the values of each fields in the list.

   The ``selection`` method should be an instance method.

   The set of field names is filled by using the decorator :meth:`depends`.

.. attribute:: Selection.translate_selection

   If ``True``, the human-readable values will be translated.

   Default value is ``True``.

.. attribute:: Selection.help_selection

   A dictionary mapping the selection value with its help string.

Class methods:

.. classmethod:: Selection.get_selection(model, name, inst)

   Returns a :py:class:`dictionary <dict>` mapping the selection value to its
   human-readable value.

.. classmethod:: Selection.get_selection_string(selection, value)

   Returns the human-readable form of ``value`` in regard to ``selection``.
   ``selection`` is acquired thanks to :meth:`Selection.get_selection`.
   ..note::
   This method should be used instead of relying on dictionary access
   because this method take into account the internal representation of the
   ``Selection`` value.

Instance methods:

.. method:: Selection.translated([name])

   Returns a descriptor for the translated value of the field.

   The descriptor must be used on the same class as the field.
   It uses the language defined in the context of the instance accessed.


MultiSelection
--------------

.. class:: MultiSelection(selection, string[, sort[, translate[, help_selection[, \**options]]]])

   A :py:class:`tuple` field with limited values to choose from.

:class:`MultiSelection` has some extra arguments:

.. attribute:: MultiSelection.selection

   Same as :attr:`Selection.selection`.

.. attribute:: MultiSelection.sort

   Same as :attr:`Selection.sort`.

.. attribute:: MultiSelection.translate_selection

   Same as :attr:`Selection.translate_selection`.

.. attribute:: MultiSelection.help_selection

   Same as :attr:`Selection.help_selection`.

Class methods:

.. classmethod:: MultiSelection.get_selection(model, name, inst)

   Same as :meth:`Selection.get_selection`

.. classmethod:: MultiSelection.get_selection_string(selection, value)

   Same as :meth:`Selection.get_selection_string`

Instance methods:

.. method:: MultiSelection.translated([name])

   Same as :meth:`Selection.translated` but returns a list of translated
   values.


Reference
---------

.. class:: Reference(string[, selection[, sort[, selection_change_with[, translate[, help_selection[,search_order[, search_context[, \**options]]]]]]]])

   A :py:class:`string <str>` field that refers to a record of a model.

      '<model name>,<record id>'

   But a ``tuple`` can be used to search or set value.

:class:`Reference` has some extra arguments:

.. attribute:: Reference.selection

   Same as :attr:`Selection.selection` but only for model name.

.. attribute:: Reference.sort

   Same as :attr:`Selection.sort`.

.. attribute:: Reference.selection_change_with

   Same as :attr:`Selection.selection_change_with`.

.. attribute:: Reference.translate_selection

   Same as :attr:`Selection.translate_selection`.

.. attribute:: Reference.help_selection

   Same as :attr:`Selection.help_selection`.

.. attribute:: Reference.datetime_field

   Same as :attr:`Many2One.datetime_field`.

.. attribute:: Reference.search_order

   A dictionary that contains a :ref:`PYSON <ref-pyson>` expression defining
   the default order used to display search results in the clients per model
   name.

.. attribute:: Reference.search_context

   Same as :attr:`Many2One.search_context`.

Instance methods:

.. method:: Reference.translated([name])

   Same as :meth:`~Selection.translated` but for the translated name of the
   target model.

.. method:: Reference.sql_id(column, Model)

   Return the SQL expression that extract the record ID of the column.


Many2One
--------

.. class:: Many2One(model_name, string[, left[, right[, path[, ondelete[, datetime_field[, search_order[, search_context[, \**options]]]]]]]])

   A many-to-one relation field that refers to a record of the named model.

   A :py:class:`integer <int>` as :attr:`~trytond.model.Model.id` is used for
   low level APIs.

:class:`Many2One` has some extra arguments:

.. attribute:: Many2One.model_name

   The name of the target model.

.. attribute:: Many2One.left

   The name of the field that stores the left value for the `Modified Preorder
   Tree Traversal`_.
   It only works if the :attr:`model_name` is the same then the model.

   .. warning::

      The MPTT Tree will be rebuild on database update if one record is found
      having left or right field value equals to the default or NULL.

.. _`Modified Preorder Tree Traversal`: http://en.wikipedia.org/wiki/Tree_traversal

.. attribute:: Many2One.right

   The name of the field that stores the right value.
   See :attr:`left`.

.. attribute:: Many2One.path

   The name of the :class:`Char` field that stores the path.
   It only works if the :attr:`model_name` is the same as the model.

   .. note::

      The path is used to optimize searches using the ``child_of`` or
      ``parent_of`` operators.

   .. warning::

      The paths in the tree will be rebuilt during the database update if any
      of the records are found to have a path field equal to the default, or
      ``NULL``.

.. attribute:: Many2One.ondelete

   Define the behavior of the record when the target record is deleted.

   Allowed values are:

      - ``CASCADE``: tries to delete the record.

      - ``RESTRICT``: prevents the deletion of the target record.

      - ``SET NULL``: clears the relation field.

    ``SET NULL`` is the default setting.

   .. note::

      ``SET NULL`` is override into ``RESTRICT`` if :attr:`~Field.required` is
      ``True``.

.. attribute:: Many2One.datetime_field

   If set, the target record will be read at the date defined by the datetime
   field name of the record.

   It is usually used in combination with
   :attr:`~trytond.model.ModelSQL._history` to request a value for a given date
   and time on a historicized model.

.. attribute:: Many2One.search_order

   A :ref:`PYSON <ref-pyson>` expression defining the default order used to
   display search results in the clients.

.. attribute:: Many2One.search_context

   A dictionary defining the default context used when searching from the
   client.

   .. note::

      ``search_context`` overrides the values from the client ``context``.


One2Many
--------

.. class:: One2Many(model_name, field, string[, add_remove[, order[, datetime_field[, size[, search_order[, search_context[, \**options]]]]]]])

   A one-to-many relation field that refers to records of the named model.

   It requires to have the opposite :class:`Many2One` field or a
   :class:`Reference` field defined on the target model.

   A :py:class:`tuple <tuple>` composed of :py:class:`integer <int>` as
   :attr:`~trytond.model.Model.id` is used for low level APIs.

:class:`One2Many` accepts as written and created value a :py:class:`list
<list>` of :py:class:`tuples <tuple>` like this:

   - ``('create', [{<field name>: value, ...}, ...])``:
     create new target records and link them to this one.

   - ``('write', ids, {<field name>: value, ...}, ...)``:
     write values to target ids.

   - ``('delete', ids)``:
     delete the target ids.

   - ``('add', ids)``:
     link the target ids to this record.

   - ``('remove', ids)``:
     unlink the target ids from this record.

   - ``('copy', ids[, {<field name>: value, ...}, ...])``:
     copy the target ids to this record.
     Optional field names and values may be added to override some of the
     fields of the copied records.

.. note::

   :class:`~trytond.pyson.PYSON` statement or :attr:`Field.depends` of target
   records can access value of the parent record fields by prepending
   ``_parent_`` to the opposite field name and followed by the dotted notation.

:class:`One2Many` has some extra arguments:

.. attribute:: One2Many.model_name

   The name of the target model.

.. attribute:: One2Many.field

   The name of the field that handles the opposite :class:`Many2One` or
   :class:`Reference`.

:class:`One2Many` has some extra arguments:

.. attribute:: One2Many.add_remove

   A :ref:`domain <topics-domain>` to select records to add.

   If set, the client will allow to add/remove existing records instead of only
   create/delete.

.. attribute:: One2Many.filter

   A :ref:`domain <topics-domain>` that is not a constraint but only a filter
   on the records.

   .. warning::

      Only a static domain is allowed, it cannot contain any
      :class:`~trytond.pyson.PYSON` statements.

.. attribute:: One2Many.order

   A list of tuple defining the default order of the records like for
   :attr:`trytond.model.ModelSQL._order`.

.. attribute:: One2Many.datetime_field

   Same as :attr:`Many2One.datetime_field`.

.. attribute:: One2Many.size

   An integer or a PYSON expression denoting the maximum number of records
   allowed in the relation.

.. attribute:: One2Many.search_order

   Same as :attr:`Many2One.search_order`.

.. attribute:: One2Many.search_context

   Same as :attr:`Many2One.search_context`.

Instance methods:

.. method:: One2Many.remove(instance, records)

   Remove the target records from the instance instead of deleting them.

Many2Many
---------

.. class:: Many2Many(relation_name, origin, target, string[, order[, datetime_field[, size[, search_order[, search_context[, \**options]]]]]])

   A many-to-many relation field that refers to records of the targeted model.

   It requires to have the opposite origin :class:`Many2One` field or a
   :class:`Reference` field defined on the relation model and a
   :class:`Many2One` field pointing to the target.

   A :py:class:`tuple <tuple>` composed of :py:class:`integer <int>` as
   :attr:`~trytond.model.Model.id` is used for low level APIs.

:class:`Many2Many` accepts as written and created value a :py:class:`list
<list>` of :py:class:`tuples <tuple>` like the :class:`One2Many`.

:class:`Many2Many` has some extra arguments:

.. attribute:: Many2Many.relation_name

   The name of the relation model.

.. attribute:: Many2Many.origin

   The name of the field that has the :class:`Many2One` or :class:`Reference`
   to the record.

.. attribute:: Many2Many.target

   The name of the field that has the :class:`Many2One` to the target record.

   .. note::

      A :class:`Many2Many` field can be used on a simple
      :class:`~trytond.model.ModelView`, like in a
      :class:`~trytond.wizard.Wizard`.
      For this, :attr:`~Many2Many.relation_name` is set to the target model and
      :attr:`~Many2Many.origin` and :attr:`~Many2Many.target` are set to
      ``None``.

:class:`Many2Many` has some extra arguments:

.. attribute:: Many2Many.order

   Same as :attr:`One2Many.order`.

.. attribute:: Many2Many.datetime_field

   Same as :attr:`Many2One.datetime_field`.

.. attribute:: Many2Many.size

   An integer or a :class:`~trytond.pyson.PYSON` expression denoting the
   maximum number of records allowed in the relation.

.. attribute:: Many2Many.add_remove

   An alias to the :attr:`~Field.domain` for compatibility with the
   :class:`One2Many`.

.. attribute:: Many2Many.filter

   Same as :attr:`One2Many.filter`.

.. attribute:: Many2Many.search_order

   Same as :attr:`Many2One.search_order`.

.. attribute:: Many2Many.search_context

   Same as :attr:`Many2One.search_context`.

Instance methods:

.. method:: Many2Many.get_relation()

   Return the relation :class:`~trytond.model.Model`.

.. method:: Many2Many.get_target()

   Return the target :class:`~trytond.model.Model`.

.. method:: Many2Many.delete(instance, records):

   Delete the target records from the instance instead of removing them.


One2One
-------

.. class:: One2One(relation_name, origin, target, string[, datetime_field[, \**options]])

   A one-to-one relation field that refers to a record of the targeted model.

   .. warning::
      It is on the relation_name :class:`~trytond.model.Model` that the unicity
      of the couple (origin, target) must be checked.

   A :py:class:`integer <int>` as :attr:`~trytond.model.Model.id` is used for
   low level APIs.

:class:`One2One` has some extra arguments:

.. attribute:: One2One.datetime_field

   Same as :attr:`Many2One.datetime_field`.

.. attribute:: One2One.filter

   Same as :attr:`One2Many.filter`.

Instance methods:

.. method:: One2One.get_relation()

   Return the relation :class:`~trytond.model.Model`.

.. method:: One2One.get_target()

   Return the target :class:`~trytond.model.Model`.


Function
--------

.. class:: Function(field, getter[, setter[, searcher[, getter_with_context]]])

   A function field can emulate any other given :class:`field <Field>`.

:class:`Function` has some extra arguments:

.. attribute:: Function.getter

   The name of the classmethod or instance of the :class:`~trytond.model.Model`
   for getting values.
   The signature of the classmethod is::

      getter(instances, name)

   where ``name`` is the name of the field, and it must return a dictionary
   with a value for each instance.

   Or the signature of the classmethod is::

      getter(instances, names)

   where ``names`` is a list of name fields, and it must return a dictionary
   containing for each names a dictionary with a value for each instance.

   The signature of the instancemethod is::

      getter(name)

   where ``name`` is the name of the field, and it must return the value.

.. attribute:: Function.setter

   The name of the classmethod of the :class:`~trytond.model.Model` to set the
   value.
   The signature of the method id::

      setter(instances, name, value)

   where ``name`` is the name of the field and ``value`` the value to set.

   .. warning::

       The modifications made to instances are not saved automatically.

.. attribute:: Function.searcher

   The name of the classmethod of the :class:`~trytond.model.Model` to search
   on the field.
   The signature of the method is::

      searcher(name, clause)

   where ``name`` is the name of the field and ``clause`` is a :ref:`domain
   clause <topics-domain>`.
   It must return a list of :ref:`domain <topics-domain>` clauses but the
   ``operand`` can be a SQL query.

.. attribute:: Function.getter_with_context

   A boolean telling if the getter result depends on the context.

   If it does not depend, the getter is called without context and the result
   is stored in the transaction cache when readonly.

   The default value is ``True``.

Instance methods:

.. method:: Function.get(ids, model, name[, values])

   Call the :attr:`~Function.getter` classmethod where ``model`` is the
   :class:`~trytond.model.Model` instance of the field, ``name`` is the name of
   the field.

.. method:: Function.set(ids, model, name, value)

   Call the :attr:`~Function.setter` classmethod where ``model`` is the
   :class:`~trytond.model.Model` instance of the field, ``name`` is the name of
   the field, ``value`` is the value to set.

.. method:: Function.search(model, name, clause)

   Call the :attr:`~Function.searcher` classmethod where ``model`` is the
   :class:`~trytond.model.Model` instance of the field, ``name`` is the name of
   the field, ``clause`` is a clause of :ref:`domain <topics-domain>`.

MultiValue
----------

.. class:: MultiValue(field)

   A multivalue field that is like a :class:`Function` field but with
   predefined :attr:`~Function.getter` and :attr:`~Function.setter` that use
   the :class:`~trytond.model.MultiValueMixin` for stored values.

.. warning::

   The :meth:`~trytond.model.MultiValueMixin.get_multivalue` and
   :meth:`~trytond.model.MultiValueMixin.set_multivalue` should be prefered
   over the descriptors of the field.

.. warning::

   The :ref:`default <topics-fields_default_value>` method of the field must
   accept pattern as keyword argument.


Dict
----

.. class:: Dict(schema_model[, \**options])

   A :py:class:`dictionary <dict>` field with predefined keys.

.. note::
    It is possible to store the dict as JSON in the database if the backend
    supports by manually altering the column type to JSON on the database.

:class:`Dict` has some extra arguments:

.. attribute:: Dict.schema_model

   The name of the :class:`~trytond.model.DictSchemaMixin` model that stores
   the definition of keys.

.. attribute:: Dict.search_unaccented

   Same as :attr:`Char.search_unaccented` but when searching on key's value.

Instance methods:

.. method:: Dict.translated([name[, type_]])

   Return a descriptor for the translated ``values`` or ``keys`` of the field
   following ``type_``.
   The descriptor must be used on the same class as the field.
   Default ``type_`` is ``values``.

fmany2one
---------

.. function:: fmany2one(name, sources, target[, string[, ondelete[, \**options]]])

Return a mixin_ class which adds a :class:`Function` field to a
:class:`~trytond.model.ModelSQL` class that emulate a :class:`Many2One` that
refers to the ``target`` record having the ``sources`` as value.
``target`` is composed of the name of the model and the name of the fields
separated by a comma.
The target fields must be unique.

.. _mixin: http://en.wikipedia.org/wiki/Mixin
