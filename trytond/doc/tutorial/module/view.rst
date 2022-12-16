.. _tutorial-module-view:

Display records
===============

Having records in the database is nice but we want the user to manage this
records through the user interface.

In order to denote that a model can be displayed in the interface, you have to
inherit from :class:`~trytond.model.ModelView`:

.. code-block:: python

    from trytond.model import ModelSQL, ModelView
    ...

    class Opportunity(ModelSQL, ModelView):
        ...

When you inherit from :class:`~trytond.model.ModelView`, your model gains the
methods required to display the data on Tryton clients.
Those methods allow to retrieve the fields and the definition of the views used
by a model, to apply attributes on view elements and they also provide all the
machinery for :ref:`on_change <tutorial-module-on-change>` and
:ref:`on_change_with <tutorial-module-on-change-with>`.

Tryton Views
------------

In Tryton data can be displayed using different kind of views.
The available view types and it's attributes are listed on the :ref:`Views
<topics-views>` topic.

Tryton views are usual Tryton records that are persisted into the database.
This design choice means that views are extendable and that you can use the
traditional Tryton concepts when interacting with them.


Define views
------------

Views are defined in XML_ files and they contain one XML tag for each element
displayed in the view.
The root tag of the view defines the view type.
An example view for our opportunity module will be as follows:

Here is the content of the form view of opportunity in
:file:`view/opportunity_form.xml`:

.. code-block:: xml

   <form>
      <label name="party"/>
      <field name="party"/>
      <label name="description"/>
      <field name="description"/>
      <label name="start_date"/>
      <field name="start_date"/>
      <label name="end_date"/>
      <field name="end_date"/>
      <separator name="comment" colspan="4"/>
      <field name="comment" colspan="4"/>
   </form>

And here is the content of the list view in :file:`view/opportunity_list.xml`:

.. code-block:: xml

   <tree>
      <field name="party"/>
      <field name="description"/>
      <field name="start_date"/>
      <field name="end_date"/>
   </tree>

The value of the ``name`` attribute for ``field`` and ``label`` tags is the
name of the field attribute of the model.
Each XML tag can contain different attributes to customize how the widgets
are displayed in the views.
The full reference can be found on the :ref:`Views <topics-views>` section.

Once a views is defined it must be registered on the Tryton database in order
to make the server know about them.
In order to do so with should register it on a :ref:`XML file
<topics-modules-xml-files>` specifying the following information:

``model``
   The name of the model of the view
``type``
   Possible values are: tree, form, calendar, graph, board
``name``
   The name of the XML file (without extension) in the :file:`view` folder
   which contains the view definition

Here is the content of the :file:`opportunity.xml` file:

.. code-block:: xml

   <tryton>
      <data>
         <record model="ir.ui.view" id="opportunity_view_form">
            <field name="model">training.opportunity</field>
            <field name="type">form</field>
            <field name="name">opportunity_form</field>
         </record>

         <record model="ir.ui.view" id="opportunity_view_list">
            <field name="model">training.opportunity</field>
            <field name="type">tree</field>
            <field name="name">opportunity_list</field>
         </record>
      </data>
   </tryton>

Now we have to declare the XML data file in the :file:`tryton.cfg` file:

.. code-block:: ini

   [tryton]
   ...
   xml:
      opportunity.xml

.. _XML: https://en.wikipedia.org/wiki/XML

Create menu entry
-----------------

In order to show our models on the user menu we need an
``ir.action.act_window`` and a menu entry.

An action window is used to relate one or more views, usually a list and a form
view.

Here is the definition of the opportunities action to append into
:file:`opportunity.xml`:

.. code-block:: xml

   <tryton>
      <data>
         ...
         <record model="ir.action.act_window" id="act_opportunity_form">
            <field name="name">Opportunities</field>
            <field name="res_model">training.opportunity</field>
         </record>
         <record model="ir.action.act_window.view" id="act_opportunity_form_view1">
            <field name="sequence" eval="10"/>
            <field name="view" ref="opportunity_view_list"/>
            <field name="act_window" ref="act_opportunity_form"/>
         </record>
         <record model="ir.action.act_window.view" id="act_opportunity_form_view2">
            <field name="sequence" eval="20"/>
            <field name="view" ref="opportunity_view_form"/>
            <field name="act_window" ref="act_opportunity_form"/>
         </record>
      </data>
   </tryton>

A menu entry is created using the special ``menuitem`` XML tag which accepts
the following values:

``id``
   Required XML identifier to refer this menu_item from other records.
``sequence``
   Used to define the order of the menus.
``action``
   The action to execute when clicking the menu.
``name``
   The string that will be shown on the menu.
   If no name is entered and an action is set, the action name will be used.
``parent``
   The parent menu when creating a sub-menu.

Lets add a menu entry to the :file:`opportunity.xml` file with:

.. code-block:: xml

   <tryton>
      <data>
         ...
         <menuitem
            name="Opportunities"
            sequence="50"
            id="menu_opportunity"/>
         <menuitem
            parent="menu_opportunity"
            action="act_opportunity_form"
            sequence="10"
            id="menu_opportunity_form"/>
      </data>
   </tryton>


Update database
---------------

As we have defined new XML records, we need to update the database with:

.. code-block:: console

   $ trytond-admin -d test --all

And restart the server and reconnect with the client to see the new menu
entries:

.. code-block:: console

   $ trytond

Let's continue with :ref:`setting default values
<tutorial-module-default-values>`.
