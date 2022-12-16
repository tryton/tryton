.. _ref-models-fields:
.. module:: trytond.model.fields

======
Fields
======

Fields define the behavior of the data on model's record.

Field options
=============

The following arguments are available to all field types. All are optional
except :attr:`Field.string`.

``string``
----------

.. attribute:: Field.string

A string for the label of the field.

``help``
--------

.. attribute:: Field.help

A multi-line help string for the field.

``required``
------------

.. attribute:: Field.required

If ``True``, the field is not allowed to be empty. Default is ``False``.

``readonly``
------------

.. attribute:: Field.readonly

If ``True``, the field is not editable in the client. Default is ``False``.

.. warning::
    For relational fields, it means only the new, delete, add and remove
    buttons are inactivated. The editable state of the target record must be
    managed at the target model level.


``domain``
----------

.. attribute:: Field.domain

A :ref:`domain <topics-domain>` constraint that will be applied on the field
value.

``states``
----------

.. attribute:: Field.states

A dictionary that defines dynamic states of the field and overrides the static
one. Possible keys are ``required``, ``readonly`` and ``invisible``.
The values are :class:`~trytond.pyson.PYSON` statements that will be evaluated
with the values of the record.

``select``
----------

.. attribute:: Field.select

If true, the content of the field will be indexed.

.. _ref-models-fields-on_change:

``on_change``
-------------

.. attribute:: Field.on_change

A set of field names. If this attribute is set, the client will call the
method ``on_change_<field name>`` of the model when the user changes the
current field value and will give the values of each fields in this list. The
method signature is::

    on_change_<field name>()

This method must change the value of the fields to be updated.

.. note::

    The on_change_<field name> methods are running in a rollbacked transaction.
..

The set of field names could be filled by using the decorator :meth:`depends`.

.. _ref-models-fields-on_change_with:

``on_change_with``
------------------

.. attribute:: Field.on_change_with

A set of field names. Same like :attr:`on_change`, but defined the other way
around. If this attribute is set, the client will call the method
``on_change_with_<field name>`` of the model when the user changes one of the
fields defined in the list and will give the values of each fields in this
list. The method signature is::

    on_change_with_<field name>()

This method must return the new value of the field.

.. note::

    The on_change_with_<field name> methods are running in a rollbacked transaction.

..

The set of field names could be filled by using the decorator :meth:`depends`.

``depends``
-----------

.. attribute:: Field.depends

A list of field names on which the current one depends. This means that the
client will also read these fields even if they are not defined on the view.
:attr:`Field.depends` is used per example to ensure that
:class:`~trytond.pyson.PYSON` statement could be evaluated.

``context``
-----------

.. attribute:: Field.context

A dictionary which will update the current context for *relation field*.

.. warning::
    The context could only depend on direct field of the record and without
    context.
..

``loading``
-----------

.. attribute:: Field.loading

Define how the field must be loaded: ``lazy`` or ``eager``.

``name``
--------

.. attribute:: Field.name

The name of the field.

Instance methods:

.. method:: Field.convert_domain(domain, tables, Model)

    Convert the simple :ref:`domain <topics-domain>` clause into a SQL
    expression or a new domain. :ref:`tables <ref-tables>` could be updated to
    add new joins.

.. method:: Field.sql_format(value)

    Convert the value to use as parameter of SQL queries.

.. method:: Field.sql_type()

    Return the namedtuple('SQLType', 'base type') which defines the SQL type to
    use for creation and casting. Or `None` if the field is not stored in the
    database.

    sql_type is using the `_sql_type` attribute to compute its return value.
    The backend is responsible for the computation.

    For the list of supported types by Tryton see 
    :ref:`backend types <topics-backend_types>`.

.. method:: Field.sql_cast(expression)

    Return the SQL expression with cast with the type of the field.

.. method:: Field.sql_column(table)

    Return the Column instance based on table.

.. method:: Field.set_rpc(model)

    Adds to `model` the default RPC instances required by the field.

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
``tables`` is a nested dictionary, see :meth:`~Field.convert_domain`.

Ordering
========

A class method could be defined for each field which must return a list of SQL
expression on which to order instead of the field.
The method signature is::

    order_<field name>(tables)

Where ``tables`` is a nested dictionary, see :meth:`~Field.convert_domain`.

Depends
=======

.. method:: depends([\*fields[, methods]])

A decorator to define the field names on which the decorated method depends.
The `methods` argument can be used to duplicate the field names from other
decorated methods. This is useful if the decorated method calls another method.

Field types
===========

Boolean
-------

.. class:: Boolean(string[, \**options])

A true/false field.

Integer
-------

.. class:: Integer(string[, \**options])

An integer field.

BigInteger
----------

.. class:: BigInteger(string[, \**options])

A long integer field.

Char
----

.. class:: Char(string[, size[, translate[, \**options]]])

A single line string field.

:class:`Char` has two extra optional arguments:

.. attribute:: Char.size

    The maximum length (in characters) of the field. The size is enforced at
    the storage level and in the client input.

.. attribute:: Char.translate

    If true, the value of the field is translatable. The value readed and
    stored will depend on the ``language`` defined in the context.

.. attribute:: Char.autocomplete

    A set of field names. If this attribute is set, the client will call the
    method ``autocomplete_<field name>`` of the model when the user changes one
    of those field value. The method signature is::

        autocomplete_<field name>()

    This method must return a list of string that will populate the
    ComboboxEntry in the client.
    The set of field names could be filled by using the decorator :meth:`depends`.

.. attribute:: Char.search_unaccented

    If this attribute is set to True, ``ilike`` searches will be performed on
    unaccented strings. The default value is True.

.. warning::

    The database backend must supports unaccented search.

Text
----

.. class:: Text(string[, size[, translatable[, \**options]]])

A multi line string field.

:class:`Text` has two extra optional arguments:

.. attribute:: Text.size

    Same as :attr:`Char.size`

.. attribute:: Text.translate

    Same as :attr:`Char.translate`

Float
-----

.. class:: Float(string[, digits[, \**options]])

A floating-point number field. It will be represented in Python by a ``float``
instance.

:class:`Float` has one extra optional arguments:

.. attribute:: Float.digits

    A tuple of two integers. The first integer defines the total of numbers in
    the integer part. The second integer defines the total of numbers in the
    decimal part.
    Integers can be replaced by a :class:`~trytond.pyson.PYSON` statement.
    If digits is None or any values of the tuple is `None`, no validation on
    the numbers will be done.

Numeric
-------

.. class:: Numeric(string[, digits[, \**options]])

A fixed-point number field. It will be represented in Python by a
``decimal.Decimal`` instance.

:class:`Numeric` has one extra optional arguments:

.. attribute:: Numeric.digits

    Same as :attr:`Float.digits`

Date
----

.. class:: Date(string[, \**options])

A date, represented in Python by a ``datetime.date`` instance.

DateTime
--------

.. class:: DateTime(string[, format, \**options])

A date and time, represented in Python by a ``datetime.datetime`` instance.
It is stored in `UTC`_ while displayed in the user timezone.

.. _`UTC`: https://en.wikipedia.org/wiki/Coordinated_Universal_Time

.. attribute:: DateTime.format

    A string format as used by strftime. This format will be used to display
    the time part of the field. The default value is `%H:%M:%S`.
    The value can be replaced by a :class:`~trytond.pyson.PYSON` statement.

Timestamp
---------

.. class:: Timestamp(string[, \**options])

A timestamp, represented in Python by a ``datetime.datetime`` instance.

Time
----

.. class:: Time(string[, format, \**options])

A time, represented in Python by a ``datetime.time`` instance.

.. attribute:: Time.format

    Same as :attr:`DateTime.format`

TimeDelta
---------

.. class:: TimeDelta(string[, converter[, \**options]])

An interval, represented in Python by a ``datetime.timedelta`` instance.

.. attribute:: TimeDelta.converter

    The name of the context key containing the time converter.
    A time converter is a dictionary with the keys: ``s`` (second), ``m``
    (minute), ``h`` (hour), ``d`` (day), ``w`` (week), ``M`` (month), ``Y``
    (year) and the value in second.

Binary
------

.. class:: Binary(string[, \**options])

A binary field. It will be represented in Python by a ``bytes`` instance.

.. warning::
    If the context contains a key composed of the model name and field name
    separated by a dot and its value is the string `size` then the read value
    is the size instead of the content.

:class:`Binary` has three extra optional arguments:

.. attribute:: Binary.filename

    Name of the field that holds the data's filename. Default value
    is an empty string, which means the data has no filename (in this case, the
    filename is hidden, and the "Open" button is hidden when the widget is set
    to "image").

.. attribute:: Binary.file_id

    Name of the field that holds the `FileStore` identifier. Default value is
    `None` which means the data is stored in the database. The field must be on
    the same table and accept `char` values.

.. warning::
    Switching from database to file-store is supported transparently. But
    switching from file-store to database is not supported without manually
    upload to the database all the files.

.. attribute:: Binary.store_prefix

    The prefix to use with the `FileStore`. Default value is `None` which means
    the database name is used.

Selection
---------

.. class:: Selection(selection, string[, sort[, selection_change_with[, translate[, \**options]]])

A string field with limited values to choice.

:class:`Selection` has one extra required argument:

.. attribute:: Selection.selection

    A list of 2-tuples that looks like this::

        [
            ('M', 'Male'),
            ('F', 'Female'),
        ]

    The first element in each tuple is the actual value stored. The second
    element is the human-readable name.

    It can also be the name of a class or instance method on the model, that
    will return an appropriate list. The signature of the method is::

        selection()

    .. note::
        The method is automaticly added to :attr:`trytond.model.Model._rpc` if
        not manually set.
    ..

:class:`Selection` has two extra optional arguments:

.. attribute:: Selection.sort

    If true, the choices will be sorted by human-readable value. Default value
    is ``True``.

.. attribute:: Selection.selection_change_with

    A set of field names. If this attribute is set, the client will call the
    ``selection`` method of the model when the user changes on of the fields
    defined in the list and will give the values of each fields in the list.
    The ``selection`` method should be an instance method.
    The set of field names could be filled by using the decorator :meth:`depends`.

.. attribute:: Selection.translate_selection

    If true, the human-readable values will be translated. Default value is
    ``True``.

Instance methods:

.. method:: Selection.translated([name])

    Returns a descriptor for the translated value of the field. The descriptor
    must be used on the same class as the field. It will use the language
    defined in the context of the instance accessed.

Reference
---------

.. class:: Reference(string[, selection[, selection_change_with[, search_order[, search_context[, \**options]]]])

A field that refers to a record of a model. It will be represented in Python by
a ``str`` instance like this::

    '<model name>,<record id>'

But a ``tuple`` can be used to search or set value.

:class:`Reference` has three extra optional arguments:

.. attribute:: Reference.selection

    Same as :attr:`Selection.selection` but only for model name.

.. attribute:: Reference.selection_change_with

    Same as :attr:`Selection.selection_change_with`.

.. attribute:: Reference.datetime_field

    Same as :attr:`Many2One.datetime_field`

.. attribute:: Reference.search_order

    Same as :attr:`Many2One.search_order`

.. attribute:: Reference.search_context

    Same as :attr:`Many2One.search_context`

Instance methods:

.. method:: Reference.translated([name])

    Same as :meth:`~Selection.translated` but for the translated name of the
    target model.

Many2One
--------

.. class:: Many2One(model_name, string[, left[, right[, ondelete[, datetime_field[, target_search[, search_order[, search_context[, \**options]]]]]]])

A many-to-one relation field.

:class:`Many2One` has one extra required argument:

.. attribute:: Many2One.model_name

    The name of the target model.

:class:`Many2One` has some extra optional arguments:

.. attribute:: Many2One.left

    The name of the field that stores the left value for the `Modified Preorder
    Tree Traversal`_.
    It only works if the :attr:`model_name` is the same then the model.

.. warning:: The MPTT Tree will be rebuild on database update if one record
    is found having left or right field value equals to the default or NULL.

.. _`Modified Preorder Tree Traversal`: http://en.wikipedia.org/wiki/Tree_traversal

.. attribute:: Many2One.right

    The name of the field that stores the right value. See :attr:`left`.

.. attribute:: Many2One.ondelete

    Define the behavior of the record when the target record is deleted.
    Allowed values are:

        - ``CASCADE``: it will try to delete the record.

        - ``RESTRICT``: it will prevent the deletion of the target record.

        - ``SET NULL``: it will empty the relation field.

    ``SET NULL`` is the default setting.

    .. note::

        ``SET NULL`` will be override into ``RESTRICT`` if
        :attr:`~Field.required` is true.
    ..

.. attribute:: Many2One.datetime_field

    If set, the target record will be read at the date defined by the datetime
    field name of the record.
    It is usually used in combination with
    :attr:`trytond.model.ModelSQL._history` to request a value for a given date
    and time on a historicized model.

.. attribute:: Many2One.target_search

    Define the kind of SQL query to use when searching on related target.
    Allowed values are:

        - ``subquery``: it will use a subquery based on the ids.

        - ``join``: it will add a join on the main query.

    ``join`` is the default value.

    .. note::

        ``join`` could improve the performance if the target has a huge amount
        of records.
    ..

.. attribute:: Many2One.search_order

    A :ref:`PYSON <ref-pyson>` expression defining the default order used to
    display search results in the clients.

.. attribute:: Many2One.search_context

    A dictionary defining the default context used when searching from the
    client.

    Beware that ``search_context`` will override the values from the client
    ``context``.

One2Many
--------

.. class:: One2Many(model_name, field, string[, add_remove[, order[, datetime_field[, size[, search_order[, search_context[, \**options]]]]]]])

A one-to-many relation field. It requires to have the opposite
:class:`Many2One` field or a :class:`Reference` field defined on the target
model.

This field accepts as written value a list of tuples like this:

    - ``('create', [{<field name>: value, ...}, ...])``: it will create new
      target records and link them to this one.

    - ``('write'[[, ids, ...], {<field name>: value, ...}, ...])``: it will
      write values to target ids.

    - ``('delete'[, ids, ...])``: it will delete the target ids.

    - ``('add'[, ids, ...])``: it will link the target ids to this record.

    - ``('remove'[, ids, ...])``: it will unlink the target ids from this
      record.

    - ``('copy', ids[, {<field name>: value, ...}])``: it will copy the target
      ids to this record. Optional field names and values may be added to
      override some of the fields of the copied records.

.. note::

    :class:`~trytond.pyson.PYSON` statement or :attr:`Field.depends` of target
    records can access value of the parent record fields by prepending
    ``_parent_`` to the opposite field name and followed by the dotted
    notation.

..

:class:`One2Many` has some extra required arguments:

.. attribute:: One2Many.model_name

    The name of the target model.

.. attribute:: One2Many.field

    The name of the field that handles the opposite :class:`Many2One` or
    :class:`Reference`.

:class:`One2Many` has some extra optional arguments:

.. attribute:: One2Many.add_remove

    A :ref:`domain <topics-domain>` to select records to add. If set, the
    client will allow to add/remove existing records instead of only
    create/delete.

.. attribute:: One2Many.filter

    A :ref:`domain <topics-domain>` that is not a constraint but only a
    filter on the records.

.. attribute:: One2Many.order

    A list of tuple defining the default order of the records like for
    :attr:`trytond.model.ModelSQL._order`.

.. attribute:: One2Many.datetime_field

    Same as :attr:`Many2One.datetime_field`

.. attribute:: One2Many.size

    An integer or a PYSON expression denoting the maximum number of records
    allowed in the relation.

.. attribute:: One2Many.search_order

    Same as :attr:`Many2One.search_order`

.. attribute:: One2Many.search_context

    Same as :attr:`Many2One.search_context`

Many2Many
---------

.. class:: Many2Many(relation_name, origin, target, string[, order[, datetime_field[, size[, search_order[, search_context[, \**options]]]]]])

A many-to-many relation field. It requires to have the opposite origin
:class:`Many2One` field or a:class:`Reference` field defined on the relation
model and a :class:`Many2One` field pointing to the target.

This field accepts as written value a list of tuples like the :class:`One2Many`.

:class:`Many2Many` has some extra required arguments:

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
    :class:`~trytond.wizard.Wizard`. For this, :attr:`~Many2Many.relation_name`
    is set to the target model and :attr:`~Many2Many.origin` and
    :attr:`~Many2Many.target` are set to `None`.
..

:class:`Many2Many` has some extra optional arguments:

.. attribute:: Many2Many.order

    Same as :attr:`One2Many.order`

.. attribute:: Many2Many.datetime_field

    Same as :attr:`Many2One.datetime_field`

.. attribute:: Many2Many.size

    An integer or a PYSON expression denoting the maximum number of records
    allowed in the relation.

.. attribute:: Many2Many.add_remove

    An alias to the :attr:`domain` for compatibility with the :class:`One2Many`.

.. attribute:: Many2Many.filter

    Same as :attr:`One2Many.filter`

Instance methods:

.. method:: Many2Many.get_target()

    Return the target :class:`~trytond.model.Model`.

.. attribute:: Many2Many.search_order

    Same as :attr:`Many2One.search_order`

.. attribute:: Many2Many.search_context

    Same as :attr:`Many2One.search_context`

One2One
-------

.. class:: One2One(relation_name, origin, target, string[, datetime_field[, \**options]])

A one-to-one relation field.

.. warning::
    It is on the relation_name :class:`~trytond.model.Model` that the
    unicity of the couple (origin, target) must be checked.
..

.. attribute:: One2One.datetime_field

    Same as :attr:`Many2One.datetime_field`

.. attribute:: One2One.filter

    Same as :attr:`One2Many.filter`

Instance methods:

.. method:: One2One.get_target()

    Return the target :class:`~trytond.model.Model`.

Function
--------

.. class:: Function(field, getter[, setter[, searcher]])

A function field can emulate any other given `field`.

:class:`Function` has a required argument:

.. attribute:: Function.getter

    The name of the classmethod or instance of the
    :class:`~trytond.model.Model` for getting values.
    The signature of the classmethod is::

        getter(instances, name)

    where `name` is the name of the field, and it must return a dictionary with
    a value for each instance.

    Or the signature of the classmethod is::

        getter(instances, names)

    where `names` is a list of name fields, and it must return a dictionary
    containing for each names a dictionary with a value for each instance.

    The signature of the instancemethod is::

        getter(name)

    where `name` is the name of the field, and it must return the value.

:class:`Function` has some extra optional arguments:

.. attribute:: Function.setter

    The name of the classmethod of the :class:`~trytond.model.Model` to set
    the value.
    The signature of the method id::

        setter(instances, name, value)

    where `name` is the name of the field and `value` the value to set.

.. warning::
    The modifications made to instances will not be saved automatically.

.. attribute:: Function.searcher

    The name of the classmethod of the :class:`~trytond.model.Model` to search
    on the field.
    The signature of the method is::

        searcher(name, clause)

    where `name` is the name of the field and `clause` is a
    :ref:`domain clause <topics-domain>`.
    It must return a list of :ref:`domain <topics-domain>` clauses but the
    ``operand`` can be a SQL query.

Instance methods:

.. method:: Function.get(ids, model, name[, values])

    Call the :attr:`~Function.getter` classmethod where `model` is the
    :class:`~trytond.model.Model` instance of the field, `name` is the name of
    the field.

.. method:: Function.set(ids, model, name, value)

    Call the :attr:`~Function.setter` classmethod where `model` is the
    :class:`~trytond.model.Model` instance of the field, `name` is the name of
    the field, `value` is the value to set.

.. method:: Function.search(model, name, clause)

    Call the :attr:`~Function.searcher` classmethod where `model` is the
    :class:`~trytond.model.Model` instance of the field, `name` is the name of
    the field, `clause` is a clause of :ref:`domain <topics-domain>`.

MultiValue
----------

.. class:: MultiValue(field)

A multivalue field that is like a :class:`Function` field but with predefined
:attr:`~Function.getter` and :attr:`~Function.setter` that use the
:class:`~trytond.model.MultiValueMixin` for stored values.

.. warning::
    The :meth:`~trytond.model.MultiValueMixin.get_multivalue` and
    :meth:`~trytond.model.MultiValueMixin.set_multivalue` should be prefered
    over the descriptors of the field.
..

.. warning::
    The :ref:`default <topics-fields_default_value>` method of the field must
    accept pattern as keyword argument.
..

Dict
----

.. class:: Dict(schema_model[, \**options])

A dictionary field with predefined keys.

.. note::
    It is possible to store the dict as JSON in the database if the backend
    supports by manually altering the column type to JSON on the database.

:class:`Dict` has one extra required argument:

.. attribute:: Dict.schema_model

    The name of the :class:`DictSchemaMixin` model that stores the definition
    of keys.

Instance methods:

.. method:: Dict.translated([name[, type_]])

    Returns a descriptor for the translated `values` or `keys` of the field
    following `type_`. The descriptor must be used on the same class as the
    field. Default `type_` is `values`.
