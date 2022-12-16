.. _topcis-fields_on_change:

===================
on_change of fields
===================

Tryton allows developers to define methods that can be called once a field's
value has changed by the user this is the :ref:`ref-models-fields-on_change`
method.  The method has the following name::

    Model.on_change_<field name>

This is an instance method, an instance of ``Model`` will be created by
using the values from the form's fields specified by the ``on_change`` list
defined on the field.

There is also a way to define a method that must update a field whenever any
field from a predefined list is modified. This list is defined by the
:ref:`ref-models-fields-on_change_with` attribute of the field. The method
that will be called has the following name::

    Model.on_change_with_<field_name>

Just like for the classic ``on_change``, an instance of ``Model`` will be
created by using the values entered in the form's fields specified by the
``on_change_with`` attribute.

on_change & on_change_with return values
----------------------------------------

The return value of the method called will depend of the type of the call that
occured. In case of an ``on_change`` the returned value will be a dictionary
whose keys are field names to be modified and whose values will be the
corresponding new value. In case of an ``on_change_with`` the returned value
will be the new value of the field.

Pay attention that the new value of a field differs according to its type.
Simple fields require the value to be of the same type as the field.

Relation fields require some more explanations:

    - a ``field.One2Many`` or a ``field.Many2Many`` will accept either:

        - a list of ``id`` denoting the new value that will replace all
          previously ids.

        - a dictionary composed of three keys: ``update``, ``add`` and
          ``remove``.

          The ``update`` key has as value a list of dictionary that denotes the
          new value of the target's fields. The lines affected by the change
          are found using the ``id`` key of the dictionary.

          The ``add`` key have as value a list of tuple, the first element is
          the index where a new line should be added, the second element is a
          dictionary using the same convention as the dictionaries for the
          ``update`` key.

          The ``remove`` key will have as value a list of ids that will be
          remove from the field.

          Records that are not yet saved receive temporary ids (negative
          integers) that can be used in with ``update`` or ``remove`` to
          interact with them.

