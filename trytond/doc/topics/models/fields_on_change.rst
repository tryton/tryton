.. _topics-fields_on_change:

===================
on_change of fields
===================

Tryton allows developers to define methods that can be called once a field's
value has been changed by the user.
The instance method has the following name::

  on_change_<field name>

An instance of :class:`~trytond.model.Model` is created by using the values
from the client's fields specified by the
:attr:`~trytond.model.fields.Field.on_change` list defined on the field.
Any change made on the instance will be pushed back to the client-side record.

There is also a way to define a method that must update the value of a field
whenever any field from a predefined list is modified.
This list is defined by the :attr:`~trytond.model.fields.Field.on_change_with`
attribute of the field.
The method that will be called has the following name::

   on_change_with_<field_name>

Just like for the classic ``on_change``, an instance of
:class:`~trytond.model.Model` is created by using the values from the client's
fields specified by the :attr:`~trytond.model.fields.Field.on_change_with`
attribute.
The returned value of the method is pushed back to the client-side record as
the new value of the field.
