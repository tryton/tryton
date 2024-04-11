.. _tutorial-module-workflow:

Define workflow
===============

Often records follow a workflow to change their state.
For example the opportunity can be converted or lost.
Tryton has a :class:`~trytond.model.Workflow` class that provides the tooling
to follow a workflow based on the field defined in
:attr:`~trytond.model.Workflow._transition_state` which is by default
``state``.

First we need to inherit from :class:`~trytond.model.Workflow` and add a
:class:`~trytond.model.fields.Selection` field to store the state of the
record:

.. code-block:: python

    from trytond.model import Workflow
    ...
    class Opportunity(Workflow, ModelSQL, ModelView):
       ...
       state = fields.Selection([
                 ('draft', "Draft"),
                 ('converted', "Converted"),
                 ('lost', "Lost"),
                 ], "State",
           required=True, readonly=True, sort=False)

       @classmethod
       def default_state(cls):
           return 'draft'

We must define the allowed transitions between states by filling the
:attr:`~trytond.model.Workflow._transitions` set with tuples using the
:meth:`~trytond.model.Model.__setup__` method:

.. code-block:: python

    class Opportunity(Workflow, ModelSQL, ModelView):
       ...
       @classmethod
       def __setup__(cls):
          super().__setup__()
          cls._transitions.update({
                    ('draft', 'converted'),
                    ('draft', 'lost'),
                    })

For each target state, we must define a
:meth:`~trytond.model.Workflow.transition` method.
For example when the opportunity is converted we fill the ``end_date`` field
with today:

.. code-block:: python

    class Opportunity(Workflow, ModelSQL, ModelView):
       ...
       @classmethod
       @Workflow.transition('converted')
       def convert(cls, opportunities):
           pool = Pool()
           Date = pool.get('ir.date')
           cls.write(opportunities, {
               'end_date': Date.today(),
               })

.. note::
   We let you define the transition method for lost.

Now we need to add a button for each transition so the user can trigger them.

We must declare the button in the :attr:`~trytond.model.ModelView._buttons`
dictionary and decorate the transition method with the
:meth:`~trytond.model.ModelView.button` to be callable from the client:

.. code-block:: python

    class Opportunity(Workflow, ModelSQL, ModelView):
        ...
        @classmethod
        def __setup__(cls):
            ...
            cls._buttons.update({
                    'convert': {},
                    'lost': {},
                    })

        @classmethod
        @ModelView.button
        @Workflow.transition('converted')
        def convert(cls, opportunities):
            ...

        @classmethod
        @ModelView.button
        @Workflow.transition('lost')
        def lost(cls, opportunities):
            ...

Every button must also be recorded in ``ir.model.button`` to define its label
(and also the :ref:`access right <topics-access_rights>`).
We must add to the ``opportunity.xml`` file:

.. code-block:: xml

   <tryton>
      <data>
         ...
         <record model="ir.model.button" id="opportunity_convert_button">
            <field name="model">training.opportunity</field>
            <field name="name">convert</field>
            <field name="string">Convert</field>
         </record>

         <record model="ir.model.button" id="opportunity_lost_button">
            <field name="model">training.opportunity</field>
            <field name="name">lost</field>
            <field name="string">Lost</field>
         </record>
      </data>
   </tryton>

Now we can add the ``state`` field and the buttons in the form view.
The buttons can be grouped under a ``group`` tag.
This is how the ``view/opportunity_form.xml`` must be adapted:

.. code-block:: xml

   <form>
      ...
      <label name="state"/>
      <field name="state"/>
      <group col="2" colspan="2" id="button">
         <button name="lost" icon="tryton-cancel"/>
         <button name="convert" icon="tryton-forward"/>
      </group>
   </form>

.. note::
   We let you add the ``state`` field on the list view.

Update database
---------------

As we have defined new fields and XML records, we need to update the database
with:

.. code-block:: shell

   $ trytond-admin -d test --all

And restart the server and reconnect with the client to test the workflow:

.. code-block:: shell

   $ trytond

Exercise
---------

As exercise we let you add a transition between ``lost`` and ``draft`` which
will clear the ``end_date``.

Let's continue with :ref:`adding more reaction with dynamic state
<tutorial-module-states>`.
