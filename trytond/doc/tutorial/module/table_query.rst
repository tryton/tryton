.. _tutorial-module-table-query:

Define aggregated model
=======================

Aggregated data are useful to analyze business.
Tryton can provide such data using :class:`~trytond.model.ModelSQL` class which
are not based on an existing table in the database but using a SQL query.
This is done by defining a :meth:`~trytond.model.ModelSQL.table_query` method
which returns a SQL ``FromItem``.

Let's create a :class:`~trytond.model.ModelSQL` which aggregate the number of
opportunity converted or lost per month.

First we create a :class:`~trytond.model.ModelSQL` class which defines a
:meth:`~trytond.model.ModelSQL.table_query` in :file:`opportunity.py`:

.. code-block:: python

    from sql import Literal
    from sql.aggregate import Count, Min
    from sql.functions import CurrentTimestamp, DateTrunc
    ...
    class OpportunityMonthly(ModelSQL, ModelView):
        "Opportunity Monthly"
        __name__ = 'training.opportunity.monthly'

        month = fields.Date("Month")
        converted = fields.Integer("Converted")
        lost = fields.Integer("Lost")

        @classmethod
        def table_query(cls):
            pool = Pool()
            Opportunity = pool.get('training.opportunity')
            opportunity = Opportunity.__table__()

            month = cls.month.sql_cast(
                DateTrunc('month', opportunity.end_date))
            query = opportunity.select(
                Literal(0).as_('create_uid'),
                CurrentTimestamp().as_('create_date'),
                Literal(None).as_('write_uid'),
                Literal(None).as_('write_date'),
                Min(opportunity.id).as_('id'),
                month.as_('month'),
                Count(
                    Literal('*'),
                    filter_=opportunity.state == 'converted').as_('converted'),
                Count(
                    Literal('*'),
                    filter_=opportunity.state == 'lost').as_('lost'),
                where=opportunity.state.in_(['converted', 'lost']),
                group_by=[month])
            return query

.. note::
   The table query must return a value for all the fields of the model but also
   a unique ``id`` and a value for the create and write fields.

.. note::
   We get the SQL table from the :meth:`~trytond.model.ModelSQL.__table__`
   method.

.. note::
   We use :meth:`~trytond.model.fields.Field.sql_cast` to convert the timestamp
   returned by ``date_trunc`` into a :py:class:`~datetime.date`.

Then as usual we register the :class:`~trytond.model.ModelSQL` class in the in
the :class:`~trytond.pool.Pool` as type ``model`` in :file:`__init__.py`:

.. code-block:: python

    def register():
        ...
        Pool.register(
            ...,
            opportunity.OpportunityMonthly,
            module='opportunity', type_='model')

And to display we create a list view and the menu entry in
:file:`opportunity.xml`:

.. code-block:: xml

   <tryton>
      <data>
         ...
         <record model="ir.ui.view" id="opportunity_monthly_view_list">
            <field name="model">training.opportunity.monthly</field>
            <field name="type">tree</field>
            <field name="name">opportunity_monthly_list</field>
         </record>

         <record model="ir.action.act_window" id="act_opportunity_monthly_form">
            <field name="name">Monthly Opportunities</field>
            <field name="res_model">training.opportunity.monthly</field>
         </record>
         <record model="ir.action.act_window.view" id="act_opportunity_monthly_form_view">
            <field name="sequence" eval="10"/>
            <field name="view" ref="opportunity_monthly_view_list"/>
            <field name="act_window" ref="act_opportunity_monthly_form"/>
         </record>

         <menuitem
            parent="menu_opportunity"
            action="act_opportunity_monthly_form"
            sequence="50"
            id="menu_opportunity_monthly_form"/>
      </data>
   </tryton>

And now the view in :file:`view/opportunity_monthly_list.xml`:

.. code-block:: xml

   <tree>
      <field name="month"/>
      <field name="converted"/>
      <field name="lost"/>
   </tree>

Update database
---------------

As we have registered new model and XML records, we need to update the database
with:

.. code-block:: console

   $ trytond-admin -d test --all

And restart the server and reconnect with the client to test computing
aggregate:

.. code-block:: console

   $ trytond

.. note::
   As you can see the model behaves like the other models, except that you can
   not create, delete nor write on them.

This is all for your first module.
If you want to learn more about Tryton, you can continue on :ref:`specific
topics <topics-index>`.
