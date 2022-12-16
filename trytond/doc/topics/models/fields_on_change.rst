.. _topcis-fields_on_change:

===================
on_change of fields
===================

Tryton allows developers to define methods that can be called once a field's
value has changed by the user this is the :ref:`ref-models-fields-on_change`
method.  The method has the following name::

    Model.on_change_<field name>

This is an instance method, an instance of ``Model`` will be created by using
the values from the form's fields specified by the ``on_change`` list defined
on the field. Any change made on the instance will be pushed back to the
client-side record.

There is also a way to define a method that must update a field whenever any
field from a predefined list is modified. This list is defined by the
:ref:`ref-models-fields-on_change_with` attribute of the field. The method
that will be called has the following name::

    Model.on_change_with_<field_name>

Just like for the classic ``on_change``, an instance of ``Model`` will be
created by using the values entered in the form's fields specified by the
``on_change_with`` attribute. The method must return the new value of the field
to push back to the client-side record.
