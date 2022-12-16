.. _tutorial-module-on-change:

React to user input
===================

Tryton provides a way to :ref:`change the value of a field
<topics-fields_on_change>` depending on other fields.
This computation is done on the server and the values are sent back to the
client.
The value is not stored on the server until the user saves the record.
This is a great way to react to user inputs.

For example, in order to set the end date of our opportunity depending on
the start date, we can add the following instance method to ``Opportunity``
class in :file:`opportunity.py` file:

.. code-block:: python

    import datetime as dt
    ...
    class Opportunity(ModelSQL, ModelView):
        ...
        @fields.depends('start_date')
        def on_change_with_end_date(self):
            if self.start_date:
                return self.start_date + dt.timedelta(days=3)

In this case the :meth:`~trytond.model.fields.depends` decorator indicates the
names of the fields which will trigger the computation when their values are
changed.
You should take care to set all the fields used to make the computation because
the server will have only access to those fields.
This ensures that the client reacts to each field the computation depends on.

We can also compute the values of other fields when some field change.
In this case we use the ``on_change_<field_name>`` function instead of
``on_change_with_<field_name>``.
The :meth:`~trytond.model.fields.depends` decorator indicates the fields that
will be available to compute the new values.
In order to set the other fields value, we must assign them to the instance and
the changes will be propagated to the client.

So for example we can compute the description and the comment of our
opportunity model depending on the party by adding this method to the
``Opportunity`` class in :file:`opportunity.py` file:

.. code-block:: python

    class Opportunity(ModelSQL, ModelView):
        ...
        @fields.depends('party', 'description', 'comment')
        def on_change_party(self):
            if self.party:
                if not self.description:
                    self.description = self.party.rec_name
                if not self.comment:
                    lines = []
                    if self.party.phone:
                        lines.append("Tel: %s" % self.party.phone)
                    if self.party.email:
                        lines.append("Mail: %s" % self.party.email)
                    self.comment = '\n'.join(lines)

Great, you have learned how to compute values depending on other fields values.
Let's continue with :ref:`adding computed fields
<tutorial-module-function-fields>`.
