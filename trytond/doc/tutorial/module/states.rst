.. _tutorial-module-states:

Add dynamic state to fields
===========================

Sometimes you want to make fields read-only, invisible or required under
certain conditions.
This can be achieved using the :attr:`~trytond.model.fields.Field.states`
attribute of the :class:`~trytond.model.fields.Field`.
It is a dictionary with the keys ``readonly``, ``invisible`` and ``required``.
The values are :class:`~trytond.pyson.PYSON` statements that are evaluated with
the values of the record.

In our example we make some fields read-only when the record is not in the
state ``opportunity``, the "End Date" required for the ``converted`` and
``lost`` state and make the comment invisible if empty:

.. code-block:: python

    class Opportunity(...):
        ...
        description = fields.Char(
            "Description", required=True,
            states={
                'readonly': Eval('state') != 'draft',
                })
        start_date = fields.Date(
            "Start Date", required=True,
            states={
                'readonly': Eval('state') != 'draft',
                })
        end_date = fields.Date(
            "End Date",
            states={
                'readonly': Eval('state') != 'draft',
                'required': Eval('state').in_(['converted', 'lost']),
                })
        party = fields.Many2One(
            'party.party', "Party", required=True,
            states={
                'readonly': Eval('state') != 'draft',
                })
        address = fields.Many2One(
            'party.address', "Address",
            domain=[
                ('party', '=', Eval('party')),
                ],
            states={
                'readonly': Eval('state') != 'draft',
                })
        comment = fields.Text(
            "Comment",
            states={
                'readonly': Eval('state') != 'draft',
                'invisible': (
                    (Eval('state') != 'draft') & ~Eval('comment')),
                })

It is also possible to set the ``readonly``, ``invisible`` and ``icon`` states
on the :attr:`~trytond.model.ModelView._buttons`.
So we can make invisible each button for the state in which the transition is
not available:

.. code-block:: python

    class Opportunity(ModelSQL, ModelView):
        ...
        @classmethod
        def __setup__(cls):
            ...
            cls._buttons.update({
                    'convert': {
                        'invisible': Eval('state') != 'draft',
                        'depends': ['state'],
                        },
                    'lost': {
                        'invisible': Eval('state') != 'draft',
                        'depends': ['state'],
                        },
                    })

.. note::
   The fields in :class:`~trytond.pyson.Eval` statement must be added to the
   ``depends`` attribute to register the field on which the states depend.

Exercise
--------

As exercise we let you define the state for the button that reset to ``draft``
state.

Let's :ref:`extend the party model <tutorial-module-extend>`.
