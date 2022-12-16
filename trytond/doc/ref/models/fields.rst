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

``domain``
----------

.. attribute:: Field.domain

A :ref:`domain <topics-domain>` constraint that will be applied on the field
value.

.. warning::

    For now it only works on relational fields like :class:`Many2One`,
    :class:`One2Many` and :class:`Many2Many`.
..

``states``
----------

.. attribute:: Field.states

A dictionary that defines dynamic states of the field and overrides the static
one. Possible keys are ``required``, ``readonly`` and ``invisible``.
The values are :class:`~trytond.pyson.PYSON` statements that will be evaluated
with the values of the record.

``change_default``
------------------

.. attribute:: Field.change_default

If true, the field can be used as condition for a custom default value.

``select``
----------

.. attribute:: Field.select

If true, the content of the field will be indexed.

``on_change``
-------------

.. attribute:: Field.on_change

A list of field names. If this attribute is set, the client will call the
method ``on_change_<field name>`` of the model when the user changes the
current field value and will give the values of each fields in this list. The
method signature is::

    on_change_<field name>(values)

This method must return a dictionary with the values of fields to be updated.

.. note::

    The on_change_<field name> methods are runnin in a rollbacked transaction.
..

``on_change_with``
------------------

.. attribute:: Field.on_change_with

A list of field names. Same like :attr:`on_change`, but defined the other way
around. If this attribute is set, the client will call the method
``on_change_with_<field name>`` of the model when the user changes one of the
fields defined in the list and will give the values of each fields in this
list. The method signature is::

    on_change_with_<field name>(values)

This method must return the new value of the field.

.. note::

    The on_change_with_<field name> methods are running in a rollbacked transaction.

..

``depends``
-----------

.. attribute:: Field.depends

A list of field names on which the current one depends. This means that the
client will also read these fields even if they are not defined on the view.
:attr:`Field.depends` is used per example to ensure that
:class:`~trytond.pyson.PYSON` statement could be evaluated.

``order_field``
---------------

.. attribute:: Field.order_field

The name of a substitute field on which the ordering of records must be done
instead of this one.
This is often used to allow ordering on :class:`Function` fields.

``context``
-----------

.. attribute:: Field.context

A dictionary which will update the current context when opening a *relation
field*.

``loading``
-----------

.. attribute:: Field.loading

Define how the field must be loaded: ``lazy`` or ``eager``.

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

    A list of field names. If this attribute is set, the client will call the
    method ``autocomplete_<field name>`` of the model when the user changes one
    of those field value. The method signature is::

        autocomplete_<field name>(values)

    This method must return a list of string that will populate the
    ComboboxEntry in the client.

.. warning::
    Note that you may need to set :attr:`Field.loading` to ``lazy``
    when :attr:`Char.translate` is ``True``.
..

Sha
---

.. class:: Sha(string[, \**options])

A string field which value will be stored with a `secure hash algorithm`_.

.. _`secure hash algorithm`: http://en.wikipedia.org/wiki/Secure_Hash_Algorithm

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

.. class:: DateTime(string[, \**options])

A date and time, represented in Python by a ``datetime.datetime`` instance.

Time
----

.. class:: Time(string[, \**options])

A time, represented in Python by a ``datetime.time`` instance.

Binary
------

.. class:: Binary(string[, \**options])

A binary field. It will be represented in Python by a ``str`` instance.

Selection
---------

.. class:: Selection(selection, string[, sort[, translate[, \**options]]])

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

    It can also be the name of a method on the model, that will return an
    appropriate list. The signature of the method is::

        selection()

    .. note::
        The method is automaticly added to :attr:`trytond.model.Model._rpc` if
        not manually set.
    ..

:class:`Selection` has two extra optional arguments:

.. attribute:: Selection.sort

    If true, the choices will be sorted by human-readable value. Default value
    is ``True``.

.. attribute:: Selection.translate_selection

    If true, the human-readable values will be translated. Default value is
    ``True``.

Reference
---------

.. class:: Reference(string[, selection[, \**options]])

A field that refers to a record of a model. It will be represented in Python by
a ``str`` instance like this::

    '<model name>,<record id>'

:class:`Reference` has one extra optional argument:

.. attribute:: Reference.selection

    Same as :attr:`Selection.selection` but only for model name.

Many2One
--------

.. class:: Many2One(model_name, string[, left[, right[, ondelete[, datetime_field[, \**options]]]]])

A many-to-one relation field.

:class:`Many2One` has one extra required argument:

.. attribute:: Many2One.model_name

    The name of the target model.

:class:`Many2One` has some extra optional arguments:

.. attribute:: Many2One.left

    The name of the field that stores the left value for the `Modified Preorder
    Tree Traversal`_.
    It only works if the :attr:`model_name` is the same then the model.

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

One2Many
--------

.. class:: One2Many(model_name, field, string[, add_remove[, order[, datetime_field[, \**options]]]])

A one-to-many relation field. It requires to have the opposite
:class:`Many2One` field defined on the target model.

This field accepts as written value a list of tuples like this:

    - ``('create', {<field name>: value, ...})``: it will create a new target
      record and link it to this one.

    - ``('write'[, ids, ...], {<field name>: value, ...})``: it will write
      values to target ids.

    - ``('delete'[, ids, ...])``: it will delete the target ids.

    - ``('delete_all')``: it will delete all the target records.

    - ``('add'[, ids, ...])``: it will link the target ids to this record.

    - ``('unlink'[, ids, ...])``: it will unlink the target ids from this
      record.

    - ``('unlink_all')``: it will unlink all the target records.

    - ``('set'[, ids, ...])``: it will link only the target ids to this record.

:class:`One2Many` has some extra required arguments:

.. attribute:: One2Many.model_name

    The name of the target model.

.. attribute:: One2Many.field

    The name of the field that handles the opposite :class:`Many2One`

:class:`One2Many` has some extra optional arguments:

.. attribute:: One2Many.add_remove

    A :ref:`domain <topics-domain>` to select records to add. If set, the
    client will allow to add/remove existing records instead of only
    create/delete.

.. attribute:: One2Many.order

    A list of tuple defining the default order of the records like for
    :attr:`trytond.model.ModelSQL._order`.

.. attribute:: One2Many.datetime_field

    Same as :attr:`Many2One.datetime_field`

Many2Many
---------

.. class:: Many2Many(relation_name, origin, target, string[, order[, datetime_field[, \**options]]])

A many-to-many relation field.

:class:`Many2Many` has some extra required arguments:

.. attribute:: Many2Many.relation_name

    The name of the relation model.

.. attribute:: Many2Many.origin

    The name of the field that has the :class:`Many2One` to the record.

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

Instance methods:

.. method:: Many2Many.get_target()

    Return the target :class:`~trytond.model.Model`.

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

Instance methods:

.. method:: One2One.get_target()

    Return the target :class:`~trytond.model.Model`.

Function
--------

.. class:: Function(field, getter[, setter[, searcher]])

A function field can emulate any other given `field`.

:class:`Function` has a required argument:

.. attribute:: Function.getter

    The name of the classmethod of the :class:`~trytond.model.Model` for
    getting values.
    The signature of the method is::

        getter(ids, name)

    where `name` is the name of the field, and it must return a dictionary with
    a value for each ids.

    Or the signature of the method is::

        getter(ids, names)

    where `names` is a list of name fields, and it must return a dictionary
    containing for each names a dictionary with a value for each ids.

:class:`Function` has some extra optional arguments:

.. attribute:: Function.setter

    The name of the classmethod of the :class:`~trytond.model.Model` to set
    the value.
    The signature of the method id::

        setter(ids, name, value)

    where `name` is the name of the field and `value` the value to set.

.. attribute:: Function.searcher

    The name of the classmethod of the :class:`~trytond.model.Model` to search
    on the field.
    The signature of the method is::

        searcher(name, clause)

    where `name` is the name of the field and `clause` is a
    :ref:`domain clause <topics-domain>`.
    It must return a list of :ref:`domain <topics-domain>` clauses.

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

Property
--------

.. class:: Property(field)

A property field that is like a :class:`Function` field but with predifined
:attr:`~Function.getter`, :attr:`~Function.setter` and
:attr:`~Function.searcher` that use the :class:`~trytond.model.ModelSQL`
`ir.property` to store values.

Instance methods:

.. method:: Property.get(ids, model, name[, values])

    Same as :meth:`Function.get`.

.. method:: Property.set(ids, model, name, value)

    Same as :meth:`Function.set`.

.. method:: Property.search(model, name, clause)

    Same as :meth:`Function.search`.
