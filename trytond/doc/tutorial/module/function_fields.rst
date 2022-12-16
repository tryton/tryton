.. _tutorial-module-function-fields:

Add computed fields
===================

Computed fields can also be defined to avoid storing duplicated data in the
database.
For example, as we have the start date and the end date of our opportunity we
can always compute the duration the opportunity lasts.
This is done with a :class:`~trytond.model.fields.Function` field, which can be
used to represent any kind of field.

Lets see how this can be done in :file:`opportunity.py` file:

.. code-block:: python

    class Opportunity(ModelSQL, ModelView):
        ...
        duration = fields.Function(
            fields.TimeDelta("Duration"), 'compute_duration')
        ...
        def compute_duration(self, name):
            if self.start_date and self.end_date:
                return self.end_date - self.start_date
            return None

The first parameter of the Function field is another
:class:`~trytond.model.fields.Field` instance which defined the type of the
field to mimic and on the second parameter, the
:attr:`~trytond.model.fields.Function.getter`, we must specify the name of the
method used to compute the value.

:class:`~trytond.model.fields.Function` fields are read-only be default, but we
can make them writable by defining a
:attr:`~trytond.model.fields.Function.setter` attribute, which is a method to
call to store the value.
Similarly we can also provide a method to search or order on them.
All the Function fields possibilities are explained on
:class:`~trytond.model.fields.Function` fields reference.

.. warning::
   If you change the start date or the end date of the opportunity, you will
   notice that the days value is not updated until the record is saved. That's
   because function fields are computed only on server side.

.. note::
   We let you add the new field to the views.

.. _tutorial-module-on-change-with:

Combine Function fields and on_change_with
------------------------------------------

On previous steps we learned how :ref:`on_change <tutorial-module-on-change>`
and :class:`~trytond.model.fields.Function` fields work.
One interesting feature is to combine them to compute and update the value.
So we can have a computed field that changes every time the user modifies one
of the values of the form.

It's a common pattern to use an ``on_change_with`` method as
:attr:`~trytond.model.fields.Function.getter` of a
:class:`~trytond.model.fields.Function` field, so the value is correctly
computed on client side and then it reacts to the user input.

In order to achieve it the following changes must be done in
:file:`opportunity.py` file:

.. code-block:: python

    class Opportunity(ModelSQL, ModelView):
        ...
        duration = fields.Function(
            fields.TimeDelta("Duration"), 'on_change_with_duration')
        ...
        @fields.depends('start_date', 'end_date')
        def on_change_with_duration(self, name=None):
            if self.start_date and self.end_date:
                return self.end_date - self.start_date
            return None

The important facts are the following:

    * Add :meth:`~trytond.model.fields.depends` decorator to react on user input
    * Change the name of the method to ``on_change_with_<field_name>``
    * Add a default None value for the name argument as it won't be supplied
      when the client updates the values reacting to user input.

Great, you designed a Function fields which reacts to the user input.
Let's go to the next step to :ref:`add domain restrictions
<tutorial-module-domains>`.
