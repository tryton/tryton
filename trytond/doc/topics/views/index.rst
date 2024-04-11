.. _topics-views:

=====
Views
=====

The views are used to display records of an :class:`ModelView
<trytond.model.ModelView>` to the user.

In Tryton, :class:`ModelView <trytond.model.ModelView>` can have several views.
An ``action`` opens a window and defines which view to show.

The views are built from XML that is stored in the :file:`view` directory of
the module or in the databases thanks to the model ir.ui.view.

So generally, they are defined in XML files with this kind of XML where name is
the name of the XML file in the :file:`view` directory:

.. highlight:: xml

::

  <record model="ir.ui.view" id="view_id">
      <field name="model">model name</field>
      <field name="type">type name</field>
      <!--field name="inherit" ref="inherit_view_id"/-->
      <!--field name="field_childs">field name</field-->
      <field name="name">view_name</field>
  </record>


There are different types of views:

.. contents::
   :local:
   :backlinks: entry
   :depth: 2

Some attributes are shared by many form elements:

.. _common-attributes-id:

``id``
   A unique identifier for the tag if there is no name attribute.

.. _common-attributes-yexpand:

``yexpand``
   A boolean to specify if the label should expand to take up any extra
   vertical space.

.. _common-attributes-yfill:

``yfill``
   A boolean to specify if the label should fill the vertical space allocated
   to it in the table cell.

.. _common-attributes-yalign:

``yalign``
   The vertical alignment, from 0.0 to 1.0.

.. _common-attributes-xexpand:

``xexpand``
   The same as ``yexpand`` but for horizontal space.

.. _common-attributes-xfill:

``xfill``
   The same as ``yfill`` but for horizontal space.

.. _common-attributes-xalign:

``xalign``
   The horizontal alignment, from ``0.0`` to ``1.0``.

.. _common-attributes-colspan:

``colspan``
   The number of columns the widget must take in the table.

.. _common-attributes-col:

``col``
   The number of columns the container must have.
   A negative value (or zero) remove the constraint on the number of columns.
   The default value is ``4``.

.. _common-attributes-states:

``states``
   A string of :ref:`PYSON statement <topics-pyson>` that is evaluated with the
   values of the current record.

   It must return a dictionary where keys can be:

   ``invisible``
      If true, the widget is hidden.

   ``required``
      If true, the field is required.

   ``readonly``
      If true, the field is readonly.

   ``icon``
      Only for button, it must return the icon name to use or False.

   ``pre_validate``
      Only for button, it contains a domain to apply on the record before
      calling the button.

   ``depends``
      Only for button, it must return the list of field on which the button
      depends.

.. _common-attributes-help:

``help``
   The string that is displayed when the cursor hovers over the widget.

.. _common-attributes-pre_validate:

``pre_validate``
   A boolean only for fields :class:`trytond.model.fields.One2Many` to specify
   if the client must pre-validate the records using
   :meth:`trytond.model.Model.pre_validate`.

.. _common-attributes-completion:

``completion``
   A boolean only for fields :class:`trytond.model.fields.Many2One`,
   :class:`trytond.model.fields.Many2Many` and
   :class:`trytond.model.fields.One2Many` to specify if the client must
   auto-complete the field.
   The default value is ``True``.

.. _common-attributes-create:

``create``
   A boolean to specify if the user can create targets from the widget.
   The default value is ``True``.

``delete``
   A boolean to specify if the user can delete targets from the widget.
   The default value is ``True``.

.. _common-attributes-factor:

``factor``
   A factor to apply on fields :class:`trytond.model.fields.Integer`,
   :class:`trytond.model.fields.Float` and
   :class:`trytond.model.fields.Numeric` to display on the widget.
   The default value is ``1``.

.. _common-attributes-symbol:

``symbol``
   Only on numerical fields, the name of field which provides the symbol to
   display.

.. _common-attributes-grouping:

``grouping``
   A boolean only on numerical fields to specify if the client must use
   grouping separators to display on the widget.
   The default value is ``True``.

.. _common-attributes-help_field:

``help_field``
   The name of Dict field mapping the Selection value with its help string.


Form
====

A form view is used to display one record.

Elements of the view are put on the screen following the rules:

    * Elements are placed on the screen from left to right, from top to bottom,
      according to the order of the XML.

    * The screen composed of a table with a fixed number of columns and enough
      rows to handle all elements.

    * Elements take one or more columns when they are put in the table. If
      there are not enough free columns on the current row, the elements are put
      at the beginning of the next row.

.. _example_form_view:

Example:

.. highlight:: xml

::

  <form col="6">
      <label name="name"/>
      <field name="name" xexpand="1"/>
      <label name="code"/>
      <field name="code"/>
      <label name="active"/>
      <field name="active" xexpand="0" width="100"/>
      <notebook colspan="6">
          <page string="General">
              <field name="addresses" mode="form,tree" colspan="4"
                  view_ids="party.address_view_form,party.address_view_tree_sequence"/>
              <label name="type"/>
              <field name="type" widget="selection"/>
              <label name="lang"/>
              <field name="lang" widget="selection"/>
              <label name="website"/>
              <field name="website" widget="url"/>
              <separator string="Categories" colspan="4"/>
              <field name="categories" colspan="4"/>
          </page>
          <page string="Accounting">
              <label name="vat_country"/>
              <field name="vat_country"/>
              <label name="vat_number"/>
              <field name="vat_number"/>
          </page>
      </notebook>
  </form>

The RNG describing the XML of a form view is stored in
``trytond/ir/ui/form.rng``.
There is also a RNC in ``trytond/ir/ui/form.rnc``.


form
----

Each form view must start with this tag with those attributes:

.. _form-attributes-on_write:

``on_write``
   The name of a method on the Model of the view that is called when a record
   is saved.
   The method must return a list of record ids that the client must reload if
   they are already loaded.
   The function must have this syntax:

      ``on_write(self, ids)``

   .. note::
      The method must be registered in :attr:`trytond.model.Model.__rpc__`.

``creatable``
   A boolean to specify if the form can be used to create new record.
   The default value is ``True``.

``cursor``
   The name of the field that must have the cursor by default.

.. _form-attributes-scan_code:

``scan_code``
  Active the scan of code using :meth:`trytond.model.ModelView.on_scan_code`.
  If the value is ``one``, only one code is requested.
  If the value is ``submit``, the form is submitted after one code.
  If the value is ``loop``, codes are requested until the user stops.
  The default value is empty.

:ref:`col <common-attributes-col>`.

.. _form-label:

label
-----

Display static string with those attributes:

``string``
   The string that is displayed in the label.

``name``
   The name of the field whose description is used for string.
   Except if ``string`` is set, it uses this value and the value of the
   field if ``string`` is empty.

:ref:`id <common-attributes-id>`,
:ref:`yexpand <common-attributes-yexpand>`,
:ref:`yfill <common-attributes-yfill>`,
:ref:`yalign <common-attributes-yalign>`,
:ref:`xexpand <common-attributes-xexpand>`,
:ref:`xfill <common-attributes-xfill>`,
:ref:`xalign <common-attributes-xalign>`,
:ref:`colspan <common-attributes-colspan>`,
:ref:`states <common-attributes-states>`,
:ref:`help <common-attributes-help>`.

It requires that either ``id`` or ``name`` is defined.

field
-----

Display a field of the object with the value of the current record with those
attributes:

``name``
   The name of the field.

``string``
   The string that is displayed for the widget.

``widget``
   The widget that must be used instead of the default one.

``help``
   The string that is displayed when the cursor stays over the widget.

``width``
   The minimum width the widget should request, or -1 to unset.

``height``
   The minimum height the widget should request, or -1 to unset.

``readonly``
   Boolean to set the field readonly.

``mode``
   It is a comma separated list, that specifies the order of the view used to
   display the relation. (Example: ``tree,form``)
   Only for :class:`~trytond.model.fields.One2Many` fields.

``view_ids``
   A comma separated list that specifies the view ids used to display the
   relation.
   For :class:`~trytond.model.fields.Many2One` and
   :class:`~trytond.model.fields.Many2Many`, the order should always be
   ``tree`` then ``form``.

``product``
   Only for :class:`~trytond.model.fields.One2Many` fields, a comma separated
   list of target field name used to create records from the Cartesian product.

``completion``
   Only for :class:`~trytond.model.fields.Many2One` fields, it is a boolean to
   set the completion of the field.

``invisible``
   The field is not displayed, but it fills cells in the table.

``filename_visible``
   Only for :class:`~trytond.model.fields.Binary` fields, boolean that enables
   the display of the filename.

``toolbar``
   Only for Rich Text widget, boolean that enables the display of the Rich Text
   toolbar.
   The default value is ``True``.

``spell``
   Only for Text widgets, a :ref:`PYSON statement <topics-pyson>` that is
   evaluated to the language code for which spell checking must be done.

``border``
   The type of border for the image widget. Available values are ``square``,
   ``rounded`` or ``circle``.
   The default value is ``square``.

``loading``
   Override the :attr:`~trytond.model.fields.Field.loading` of the field.
   When ``eager`` for :class:`~trytond.model.fields.One2Many` and
   :class:`~trytond.model.fields.Many2Many` the client may try to read the
   fields of the related model using dotted notation.
   This result in less round trip between the client and the server at the
   expense of a bigger payload and a bigger query execution time.

:ref:`yexpand <common-attributes-yexpand>`,
:ref:`yfill <common-attributes-yfill>`,
:ref:`xexpand <common-attributes-xexpand>`,
:ref:`xfill <common-attributes-xfill>`,
:ref:`colspan <common-attributes-colspan>`,
:ref:`help <common-attributes-help>`,
:ref:`pre_validate <common-attributes-pre_validate>`,
:ref:`completion <common-attributes-completion>`,
:ref:`factor <common-attributes-factor>`,
:ref:`symbol <common-attributes-symbol>`,
:ref:`help_field <common-attributes-help_field>`.

.. _form-image:

image
-----

Display an image with those attributes:

``type``
   The type of image source. Available values are ``icon`` or ``url``.
   The default value is ``icon``.

``name``
   The image name or the field name which contains the image name.
   For the ``icon`` type it must be the name of a record of ``ir.ui.icon``.
   For the ``url`` type it must be the URL. It can be relative to the server.

``url_size``
   The name of the size parameter to add to the URL.

``size``
   The size of the image in pixels.
   The default value is ``48``.

``border``
   The type of border for the image. Available values are ``square``,
   ``rounded`` or ``circle``.
   The default value is ``square``.

:ref:`yexpand <common-attributes-yexpand>`,
:ref:`yfill <common-attributes-yfill>`,
:ref:`colspan <common-attributes-colspan>`,
:ref:`states <common-attributes-states>`,
:ref:`help <common-attributes-help>`.

.. _form-separator:

separator
---------

Display a horizontal separator with those attributes:

``string``
   The string that is displayed above the separator.

``name``
   The name of the field from which the description is used for string.

:ref:`id <common-attributes-id>`,
:ref:`yexpand <common-attributes-yexpand>`,
:ref:`yfill <common-attributes-yfill>`,
:ref:`colspan <common-attributes-colspan>`,
:ref:`states <common-attributes-states>`,
:ref:`help <common-attributes-help>`.

It requires that either ``id`` or ``name`` is defined.

.. _form-newline:

newline
-------

Force to use a new row.


.. _form-button:

button
------

Display a button with those attributes:

``name``
   The name of the function that is called on click.
   The function must have this syntax:

        ``button(cls, records)``

   The function may return an ``ir.action`` id or one of those client side
   action keywords:

   .. _topics-views-client-actions:

   ``new``
      to create a new record
   ``delete``
      to delete the selected records
   ``remove``
      to remove the record if it has a parent
   ``copy``
      to copy the selected records
   ``next``
      to go to the next record
   ``previous``
      to go to the previous record
   ``close``
      to close the current tab
   ``switch <view type> [<view id>]``
      to switch the view
   ``reload``
      to reload the current tab
   ``reload context``
      to reload user context
   ``reload menu``
      to reload menu

``icon``
   The name of an icon to display in the button.

``confirm``
   A text that is displayed in a confirmation pop-up when the button is
   clicked.

``keyword``
   Specify where the button is displayed in the client toolbar.
   The valid values are the keywords starting with ``form_`` from :ref:`Actions
   <topics-actions>` without the ``form_`` part.

:ref:`colspan <common-attributes-colspan>`,
:ref:`states <common-attributes-states>`,
:ref:`help <common-attributes-help>`.

.. warning::
    The button should be registered on ``ir.model.button`` where the default
    value of the ``string``, ``confirm`` and ``help`` attributes can be can be
    defined.

.. _form-link:

link
----

Display an ``ir.action.act_window`` as a button with a counter or one counter
per tab.
When clicked it opens the window.
The available attributes are:

``name``
   The XML id of ``ir.action.act_window``.

``icon``
   The name of the icon to display.

``empty``
   If set to ``hide`` the button is not displayed if the counter is zero.
   The default is ``show``.

:ref:`colspan <common-attributes-colspan>`,
:ref:`states <common-attributes-states>`.

.. _form-notebook:

notebook
--------

Display a notebook which can contain ``page`` tags with the attributes:

:ref:`colspan <common-attributes-colspan>`,
:ref:`states <common-attributes-states>`.

.. _form-page:

page
----

Define a tab inside a ``notebook`` with the attributes:

``string``
   The string that is displayed in the tab.

``angle``
   The angle in degrees between the baseline of the label and the horizontal,
   measured counterclockwise.

:ref:`col <common-attributes-col>`,
:ref:`id <common-attributes-id>`,
:ref:`states <common-attributes-states>`.

It requires that either ``id`` or ``name`` is defined.

.. _form-group:

group
-----

Group widgets inside a sub-form with the attributes:

``string``
   If set a frame is drawn around the field with a label containing the string.
   Otherwise, the frame is invisible.

``rowspan``
   The number of rows the group spans in the table.

``expandable``
   If this attribute is present the content of the group is expandable by the
   user to reveal its content.
   A value of ``1`` means that the group starts expanded, a value of ``0``
   means that the group starts unexpanded.
   There is no default value.

``homogeneous``
   If ``True`` all the tables cells are the same size.


:ref:`col <common-attributes-col>`,
:ref:`id <common-attributes-id>`,
:ref:`yexpand <common-attributes-yexpand>`,
:ref:`yfill <common-attributes-yfill>`,
:ref:`yalign <common-attributes-yalign>`,
:ref:`xexpand <common-attributes-xexpand>`,
:ref:`xfill <common-attributes-xfill>`,
:ref:`xalign <common-attributes-xalign>`,
:ref:`colspan <common-attributes-colspan>`,
:ref:`states <common-attributes-states>`.

It requires that either ``id`` or ``name`` is defined.

.. _form-paned:

hpaned, vpaned
--------------

``position``
   The pixel position of divider, a negative value means that the position is
   unset.

:ref:`id <common-attributes-id>`,
:ref:`colspan <common-attributes-colspan>` (the default value is ``4``).

.. _form-child:

child
-----

Define the two children of a ``hpaned`` or ``vpaned``.

Tree
====

A tree view is used to display records inside a list or a tree.

It is a tree if there is a ``field_childs`` defined and this tree has the drag
and drop activated if the ``field_childs`` and the ``parent field`` are defined
in the ``ir.ui.view`` record.

The columns of the view are put on the screen from left to right.

.. _example_tree_view:

Example:

.. highlight:: xml

::

  <tree sequence="sequence">
      <field name="name"/>
      <field name="percentage">
          <suffix name="percentage" string="%"/>
      </field>
      <field name="group"/>
      <field name="type"/>
      <field name="active"/>
      <field name="sequence" tree_invisible="1"/>
  </tree>

The RNG that describes the XML for a tree view is stored in
``trytond/ir/ui/tree.rng``.
There is also a RNC in ``trytond/ir/ui/tree.rnc``.


tree
----

Each tree view must start with this tag with those attributes:

``editable``
   A boolean to specify if the list is editable.

``creatable``
   A boolean to specify if the editable list can be used to create new record.
   The default value is ``true``.

``sequence``
   The name of the field that is used for sorting.
   This field must be an integer and it is updated to match the new sort order
   when the user uses "Drag and Drop" on list rows.

``keyword_open``
   A boolean to specify if the client should look for a tree_open action on
   double click instead of switching view.

``tree_state``
   A boolean to specify if the client should save the state of the tree.

``visual``
   A :ref:`PYSON statement <topics-pyson>` that is evaluated as string
   ``muted``, ``success``, ``warning`` or ``danger`` with the context of the
   record to provide a visual context to the row.

:ref:`on_write <form-attributes-on_write>`.

field
-----

``name``
   The name of the field.

``readonly``
   A boolean to set the field readonly.

``widget``
   The widget that must be used instead of the default one.

``tree_invisible``
   A string of :ref:`PYSON statement <topics-pyson>` that is evaluated as
   boolean with the context of the view to display or not the column.

``optional``
   A boolean to define if the column is hidden or not.
   Defining the optional attribute allows each user to show/hide the column.
   The attribute value is used as default when the user has no custom setting
   for it.

``visual``
   A :ref:`PYSON statement <topics-pyson>` that is evaluated as string
   ``muted``, ``success``, ``warning`` or ``danger`` with the context of the
   record to provide a visual context to the field.

``icon``
   The name of the field that contains the name of the icon to display in the
   column.

``sum``
   A boolean to display the sum of all the records.

``width``
   The width of the column.

``expand``
   An integer that specifies if the column should be expanded to take available
   extra space in the view.
   This space is shared proportionally among all columns that have their
   ``expand`` attribute set.
   Resize doesn't work if this option is enabled.

:ref:`pre_validate <common-attributes-pre_validate>`,
:ref:`completion <common-attributes-completion>`,
:ref:`factor <common-attributes-factor>`,
:ref:`symbol <common-attributes-symbol>`,
:ref:`help_field <common-attributes-help_field>`.

prefix, suffix
--------------

A ``field`` could contain one or many ``prefix`` or ``suffix`` that is
displayed in the same column with the attributes:

``string``
   The text that is displayed.

``name``
   The name of the field whose value is displayed.

``icon``
   The image name or the field name which contains the image name.
   For the ``icon`` type it must be the name of a record of ``ir.ui.icon``.
   For the ``url`` type it must be the URL and it can be relative to the server.

``icon_type``
   The type of icon source. Available values are ``icon`` or ``url``.
   The default value is ``icon``.

``url_size``
   The name of the size parameter to add to the URL.

``border``
   The type of border for the icon. Available values are ``square``,
   ``rounded`` or ``circle``.
   The default value is ``square``.

button
------

Same as form-button_ with the addition of:

``width``
   The width of the column.

List-Form
=========

A List-forms view displays records as a list of editable forms.
It uses the same schema as the form views.

.. note:: The performance of the list-form does not allow to scale well for
          large number of records

Graph
=====

A graph view is used to display records in graph.

.. _example_graph_view:

Example:

.. highlight:: xml

::

  <graph string="Invoice by date" type="vbar">
    <x>
        <field name="invoice_date"/>
    </x>
    <y>
        <field name="total_amount"/>
    </y>
  </graph>


The RNG that describes the XML for a graph view is stored in
``trytond/ir/ui/graph.rng``.
There is also a RNC in ``trytond/ir/ui/graph.rnc``.

graph
-----

Each graph view must start with this tag with those attributes:

``type``
   The type of graph: ``vbar``, ``hbar``, ``line``, ``pie``.

``background``
   An hexadecimal value for the color of the background.

``color``
   The main color.

``legend``
   A boolean to specify if the legend must be displayed.

x, y
----

Describe the field that must be used for axis.
``x`` must contain only one tag ``field`` and ``y`` must at least one but may
contain many.

field
-----

``name``
   The name of the field on the record to use.

``string``
   The string to use as label for the field.

``key``
   Used to distinguish fields with the same name but with different domain.

``domain``
   A :ref:`PySON statement <topics-pyson>` which is evaluated with the record
   value as context.
   If the result is true the field value is added to the graph.

``fill``
   Define if the graph is filled.

``empty``
   Define if the line graph must put a point for missing dates.

``color``
   The color of the field.

``interpolation``
   Define how the line graph must interpolate points.
   The default is ``linear``.

   ``constant-center``
      Use the value of the nearest point, see `Nearest-neighbor interpolation`_

   ``constant-left``
      Use the value of the nearest left point.

   ``constant-right``
      Use the value of the nearest right point.

   ``linear``
      See `linear interpolation`_

.. _`Nearest-neighbor interpolation`:
    http://en.wikipedia.org/wiki/Nearest-neighbor_interpolation
.. _`linear interpolation`: http://en.wikipedia.org/wiki/Linear_interpolation


Board
=====

Board view is used to display multiple views at once.

Elements are put on the screen following the same rules as for ``Form`` view.

The views can be updated by the selection of records on an other view inside
the same board by using in the domain the ``active_id`` or ``active_ids`` from
the ``_actions`` dictionary with the action id of the other view as key.
For example:
.. highlight:: xml

::

   <field
      name="domain"
      pyson="1"
      eval="[('field', '=', Eval('_actions', {}).get('module.action_id', {}).get('active_id'))]"/>

The RNG that describes the XML for a board view is stored in
``trytond/ir/ui/board.rng``.
There is also a RNC in ``trytond/ir/ui/graph.rnc``.

board
-----

Each board view must start with this tag with the attribute:

:ref:`col <common-attributes-col>`.

image
-----

Same as form-image_.

separator
---------

Same as form-separator_.

label
-----

Same as form-label_.

newline
-------

Same as form-newline_.

notebook
--------

Same as form-notebook_.

page
----

Same as form-page_.

group
-----

Same as form-group_.

hpaned, vpaned
--------------

Same as form-paned_.

child
-----

Same as form-child_.

action
------

``name``
   The id of the action window.

:ref:`colspan <common-attributes-colspan>`.

Calendar
========

Calendar view is use to display records as events on a calendar based on a
``dtstart`` and optionally a ``dtend``.

Example:

.. highlight:: xml

::

  <calendar dtstart="planned_date">
      <field name="code"/>
      <field name="product"/>
      <field name="reference"/>
  </calendar>

The RNG that describes the XML for a calendar view is stored in
``trytond/ir/ui/calendar.rng``.
There is also a RNC in ``trytond/ir/ui/calendar.rnc``.

The ``calendar_scroll_time`` context key determines the initial time to scroll
to.
The default value is ``datetime.time(6)``.

calendar
--------

Each calendar view must start with this tag with those attributes:

``dtstart``
   The name of the field that contains the start date.

``dtend``
   The name of the field that contains the end date.

``mode``
   An optional name for the mode that is used first.
   Available views are: ``day``, ``week`` and ``month``.
   The default value is ``month``.

``editable``
   A boolean to specify if the calendar is editable.
   The default value is ``True``.

``color``
   An optional field name that contains the text color for the event.
   The default value is ``black``.

``background_color``
   An optional field name that contains the background color for the event.
   The default value is ``lightblue``.

``width``
   The minimum width the calendar should request, use -1 to unset.

``height``
   The minimum height the calendar should request, use -1 to unset.

field
-----

``name``
   The name of the field.
