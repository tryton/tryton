.. _tutorial-module-wizard:

Create wizard
=============

Sometime you want to add functionalities to a model that do not suite the use
of a button.
For this kind of use case the :ref:`wizard <topics-wizard>` is the preferred
solution.
A wizard is a kind of `state machine`_ where states can be a form view, an
action or transition.

.. _state machine: https://en.wikipedia.org/wiki/Finite-state_machine

Let's create a wizard that converts the opportunities by asking for the end date.

First we define a :class:`~trytond.model.ModelView` class in
:file:`opportunity.py`:

.. code-block:: python

    class ConvertStart(ModelView):
        "Convert Opportunities"
        __name__ = 'training.opportunity.convert.start'

        end_date = fields.Date("End Date", required=True)

And we register it in the :class:`~trytond.pool.Pool` in :file:`__init__.py`:

.. code-block:: python

    def register():
        Pool.register(
            ...,
            opportunity.ConvertStart,
            module='opportunity', type_='model')

Then the form view record in :file:`opportunity.xml`:

.. code-block:: xml

   <tryton>
      <data>
         ...

         <record model="ir.ui.view" id="opportunity_convert_start_view_form">
            <field name="model">training.opportunity.convert.start</field>
            <field name="type">form</field>
            <field name="name">opportunity_convert_start_form</field>
         </record>
      </data>
   </tryton>

And the view in :file:`view/opportunity_convert_start_form.xml`:

.. code-block:: xml

   <form col="2">
      <label string="Convert Opportunities?" id="convert_opportunities" colspan="2" xalign="0"/>
      <label name="end_date"/>
      <field name="end_date"/>
   </form>

Now we can define the :class:`~trytond.wizard.Wizard` with a ``start``
:class:`~trytond.wizard.StateView` for the form and a ``convert``
:class:`~trytond.wizard.StateTransition` in :file:`opportunity.py`:

.. code-block:: python

    from trytond.wizard import Wizard, StateView, StateTransition, Button
    ...
    class Opportunity(...):
        ...
        @classmethod
        @Workflow.transition('converted')
        def convert(cls, opportunities, end_date=None):
            pool = Pool()
            Date = pool.get('ir.date')
            cls.write(opportunities, {
                'end_date': end_date or Date.today(),
                })
    ...
    class Convert(Wizard):
        "Convert Opportunities"
        __name__ = 'training.opportunity.convert'

        start = StateView(
            'training.opportunity.convert.start',
            'opportunity.opportunity_convert_start_view_form', [
                Button("Cancel", 'end', 'tryton-cancel'),
                Button("Convert", 'convert', 'tryton-ok', default=True),
                ])
        convert = StateTransition()

        def transition_convert(self):
            self.model.convert(self.records, self.start.end_date)
            return 'end'

.. note::
   We added an optional ``end_date`` to the convert method.

And we register it in the :class:`~trytond.pool.Pool` as type ``wizard`` in
:file:`__init__.py`:

.. code-block:: python

    def register():
        ...
        Pool.register(
            opportunity.Convert,
            module='opportunity', type_='wizard')

Finally we just need to create a ``ir.action.wizard`` and ``ir.action.keyword``
in :file:`opportunity.xml`:

.. code-block:: xml

   <tryton>
      <data>
         ...
         <record model="ir.action.wizard" id="act_convert_opportunities">
            <field name="name">Convert Opportunities</field>
            <field name="wiz_name">training.opportunity.convert</field>
            <field name="model">training.opportunity</field>
         </record>
         <record model="ir.action.keyword" id="act_convert_opportunities_keyword">
            <field name="keyword">form_action</field>
            <field name="model">training.opportunity,-1</field>
            <field name="action" ref="act_convert_opportunities"/>
         </record>
      </data>
   </tryton>

The ``ir.action.wizard`` links the :class:`~trytond.wizard.Wizard` with the
:class:`~trytond.model.Model`.

``name``
   The string that is shown on the menu.
``wiz_name``
   The name of the :class:`~trytond.wizard.Wizard`.
``model``
   The name of the :class:`~trytond.model.Model`.

And the ``ir.action.keyword`` makes the :class:`~trytond.wizard.Wizard`
available as action to any ``training.opportunity``.

``keyword``
   The type of `keyword <topics-actions>`.
``model``
   The model or record for which the action must be displayed.
   Use ``-1`` as id for any record.
``action``
   The link to the action.

Update database
---------------

As we have defined new fields and XML records, we need to update the database
with:

.. code-block:: console

   $ trytond-admin -d test --all

And restart the server and reconnect with the client to test the wizard:

.. code-block:: console

   $ trytond

Let's create a :ref:`a report to print opportunities <tutorial-module-report>`.
