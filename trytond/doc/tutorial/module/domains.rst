.. _tutorial-module-domains:

Add domain restriction to fields
================================

One common requirement is to add restrictions to the possible value of a field.
For example we can define the following restrictions:

* The value of a numeric field must be greater that zero.
* The value of another field must be greater than the value of other.
* Related record must have fields with specific values.
  For example allow to select only products of kind *service*.

This is represented using a domain clause.
The domain clause syntax is explained on :ref:`domain reference
<topics-domain>`.

A very interesting thing of the domain, is that the client evaluates them, so:

* If we set a value that invalidate the domain of some fields, they are marked.
  A notification is displayed before saving.
* When searching for a related record, only the records that satisfy the domain
  are available.
  So it is not possible to select invalid records.
* When creating a new related record, the client automatically enforces only
  valid values.
  Fields that can have only one value are filled and set read only.

For example, it may be interesting to add the address of the party on our
``Opportunity`` model.
In this case we are interested on selecting only the addresses related to the
party.

Lets see how to do it:

.. code-block:: python

    from trytond.pyson import Eval
    ...
    class Opportunity(ModelSQL, ModelView):
        ...
        address = fields.Many2One(
            'party.address', "Address",
            domain=[
                ('party', '=', Eval('party', -1)),
                ])

The domain uses the value of the party field with the
:class:`~trytond.pyson.Eval` object.
This defines a relation between party and address field.

.. note::
   It is up to you to add the new field to the views and update the database.

Using conditional domains
-------------------------

Sometimes it is interesting to apply a domain only if another field is set.
For example we want to ensure the start date is before the end date but both
fields are optionals, so we don't want to apply any domain if they are empty.
This can be solved by using a conditional domain.

Lets see how we can achieve it:

.. code-block:: python

    from trytond.pyson import If, Bool, Eval
    ...
    class Opportunity(ModelSQL, ModelView):
        ...
        start_date = fields.Date(
            "Start Date", required=True,
            domain=[
                If(Bool(Eval('end_date')),
                    ('start_date', '<=', Eval('end_date')),
                    ())])
        end_date = fields.Date(
            "End Date",
            domain=[
                If(Bool(Eval('end_date')),
                    ('end_date', '>=', Eval('start_date')),
                    ())])

In this case we used the following statements:

* :class:`~trytond.pyson.If` which expects three values:
  (condition, true-statement, false-statement)
  In this case we use to return a domain on when the condition is ``True`` and
  return an empty domain on ``False``.
* :class:`~trytond.pyson.Bool` used to convert the field value into boolean.

All of the domains are :ref:`PSYON <ref-pyson>` statements.

Great, you have learned to add constraint on the fields value.
Let's continue with :ref:`adding a workflow <tutorial-module-workflow>`.
