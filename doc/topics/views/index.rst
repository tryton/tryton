.. _topics-views:

=====
Views
=====

The views are used to display records of an object to the user.

In Tryton, objects can have several views. An `action` opens a window and
defines which view to show.

The views are built from XML that is stored in the databases with the object
ir.ui.view.

So generally, they are defined in xml files with this kind of xml:

.. highlight:: xml

::

  <record model="ir.ui.view" id="view_id">
      <field name="model">model name</field>
      <field name="type">type name</field>
      <!--field name="inherit" ref="inherit_view_id"/-->
      <!--field name="field_childs">field name</field-->
      <field name="arch" type="xml">
          <![CDATA[
          View XML ...
          ]]>
      </field>
  </record>


There is three types of views:

    * Form

    * Tree

    * Graph

Form view
=========

The RNG describing the xml of a form view is stored in trytond/ir/ui/form.rng.
There is also a RNC in trytond/ir/ui/form.rnc.

A form view is used to display one record of an object.

Elements of the view are put on the screen following the rules:

    * Elements are placed on the screen from left to right, from top to bottom,
      according to the order of the xml.

    * The screen composed of a table with a fixed number of columns and enough
      rows to handle all elements.

    * Elements take one or more columns when they are put in the table. If
      there are not enough free columns on the current row, the elements are put
      at the begining of the next row.


XML description
---------------

List of attributes shared by many form elements:

    .. _common-attributes-id:

    * ``id``: A unique identifier for the tag if there is no name attribute.

    .. _common-attributes-yexpand:

    * ``yexpand``: A boolean to specify if the label should expand to take up
      any extra vertical space.

    .. _common-attributes-yfill:

    * ``yfill``: A boolean to specify if the label should fill the vertical
      space allocated to it in the table cell.

    .. _common-attributes-yalign:

    * ``yalign``: The vertical alignment, from 0.0 to 1.0.

    .. _common-attributes-xexpand:

    * ``xexpand``: The same as yexpand but for horizontal space.

    .. _common-attributes-xfill:

    * ``xfill``: The same as yfill but for horizontal space.

    .. _common-attributes-xalign:

    * ``xalign``: The horizontal alignment, from 0.0 to 1.0.

    .. _common-attributes-colspan:

    * ``colspan``: The number of columns the widget must take in the table.

    .. _common-attributes-states:

    * ``states``: A string of :ref:`PYSON statement <topics-pyson>` that will
      be evaluated with the values of the current record.

      It must return a dictionary where keys can be:

        * ``invisible``: If true, the widget will be hidden.

        * ``required``: If true, the field will be required.

        * ``readonly``: If true, the field will be readonly.

        * ``icon``: Only for button, it must return the icon name to use or
          False.

    .. _common-attributes-help:

    * ``help``: The string that will be displayed when the cursor hovers over
      the widget.


form
^^^^

Each form view must start with this tag.

    * ``string``: The text that will be used as default title for the tab or
      the window.

    * ``on_write``: The name of a function that will be called when the record
      is saved.  The function must have this syntax:

      ``on_write(self, ids)``

    * ``col``: The number of columns for the view.

    * ``cursor``: The name of the field that must have the cursor by default.

label
^^^^^

Display static string.

    * ``string``: The string that will be displayed in the label.

    * ``name``: The name of the field whose description will be used for
      string.

    * ``id``: see common-attributes-id_.

    * ``yexpand``: see in common-attributes-yexpand_.

    * ``yfill``: see in common-attributes-yfill_.

    * ``yalign``: see in common-attributes-yalign_.

    * ``xexpand``: see in common-attributes-xexpand_.

    * ``xfill``: see in common-attributes-xfill_.

    * ``xalign``: see in common-attributes-xalign_.

    * ``colspan``: see in common-attributes-colspan_.

    * ``states``: see in common-attributes-states_.

    * ``help``: see in common-attributes-help_.

    * Requires that either ``id`` or ``name`` is defined.

field
^^^^^

Display a field of the object with the value of the current record.

    * ``name``: The name of the field.

    * ``widget``: The widget that must be used instead of the default one.

    * ``help``: The string that will be displayed when the cursor stays over the
      widget.

    * ``width``: The minimum width the widget should request, or -1 to unset.

    * ``height``: The minimum height the widget should request, or -1 to unset.

    * ``readonly``: Boolean to set the field readonly.

    * ``required``: Boolean to set the field required.

    * ``mode``: Only for One2Many fields: it is a comma separated list, that
      specifies the order of the view used to display the relation. (Example:
      ``tree,form``)

    * ``completion``: Only for Many2One fields, it is a boolean to set the
      completion of the field.

    * ``invisible``: The field will not be displayed, but it will fill cells in
      the table.

    * ``domain``: Only for One2Many, Many2One, Many2Many fields, it defines the
      domain that must be used when searching for related records.

    * ``yexpand``: see in common-attributes-yexpand_.

    * ``yfill``: see in common-attributes-yfill_.

    * ``xexpand``: see in common-attributes-xexpand_.

    * ``xfill``: see in common-attributes-xfill_.

    * ``colspan``: see in common-attributes-colspan_.

    * ``help``: see in common-attributes-help_.

image
^^^^^

Display an image.

    * ``name``: the name of the image. It must be the name with the extension
      of an image from ``tryton/share/pixmaps/``.

    * ``yexpand``: see in common-attributes-yexpand_.

    * ``yfill``: see in common-attributes-yfill_.

    * ``colspan``: see in common-attributes-colspan_.

    * ``states``: see in common-attributes-states_.

    * ``help``: see in common-attributes-help_.


separator
^^^^^^^^^

Display a horizontal separator.

    * ``string``: The string that will be displayed above the separator.

    * ``name``: The name of the field from which the description will be used
      for string.

    * ``id``: see in common-attributes-id_.

    * ``yexpand``: see in common-attributes-yexpand_.

    * ``yfill``: see in common-attributes-yfill_.

    * ``colspan``: see in common-attributes-colspan_.

    * ``states``: see in common-attributes-states_.

    * ``help``: see in common-attributes-help_.

    * Requires that either ``id`` or ``name`` is defined.

newline
^^^^^^^

Force to use a new row.

button
^^^^^^

Display a button.

    * ``string``: The string that will be displayed inside the button.

    * ``type``: It can be ``workflow``, ``object`` or ``action``. The default
      is ``workflow``.  It defines which type of action must be run when
      clicking on it.

    * ``name``: The name of the action:

        * ``workflow``: the name of the signal that will be sent.

        * ``object``: the name of the function that will called.  The function
          must have this syntax:

          ``button(self, ids)``

        * ``action``: the id of the ir.action that will be called.

    * ``icon``

    * ``confirm``: A text that will be displayed in a confirmation popup when
      the button is clicked.

    * ``colspan``: see in common-attributes-colspan_.

    * ``states``: see in common-attributes-states_.

    * ``help``: see in common-attributes-help_.

notebook
^^^^^^^^

It adds a notebook widget which can contain page tags.

    * ``tabpos``: It can be ``up``, ``down``, ``left``, ``right``.

    * ``colspan``: see in common-attributes-colspan_.

page
^^^^

Define a new tab inside a notebook.

    * ``string``: The string that will be displayed in the tab.

    * ``angle``: The angle in degrees between the baseline of the label and the
      horizontal, measured counterclockwise.

    * ``col``: The number of columns for the page view.

    * ``id``: see in common-attributes-id_.

    * ``states``: see in common-attributes-states_.

    * Requires that either ``id`` or ``name`` is defined.

group
^^^^^

Create a sub-table in a cell.

    * ``string``: If set a frame will be drawn around the field with a label
      containing the string. Otherwise, the frame will be invisible.

    * ``rowspan``: The number of rows the group spans in the table.

    * ``col``: The number of columns for the group contains.

    * ``id``: see in common-attributes-id_.

    * ``yexpand``: see in common-attributes-yexpand_.

    * ``yfill``: see in common-attributes-yfill_.

    * ``colspan``: see in common-attributes-colspan_.

    * ``states``: see in common-attributes-states_.

    * Requires that either ``id`` or ``name`` is defined.

hpaned, vpaned
^^^^^^^^^^^^^^

    * ``position``: The pixel position of divider, a negative value means that
      the position is unset.

    * ``id``: see in common-attributes-id_.

    * ``colspan``: see in common-attributes-colspan_. The default
      for panes is 4 columns.

child1, child2
^^^^^^^^^^^^^^

Contains the two childs of a hpaned or vpaned.

.. _example_form_view:

Example
-------

.. highlight:: xml

::

  <form string="Party" col="6">
      <label name="name"/>
      <field name="name" xexpand="1"/>
      <label name="code"/>
      <field name="code"/>
      <label name="active"/>
      <field name="active" xexpand="0" width="100"/>
      <notebook colspan="6">
          <page string="General">
              <field name="addresses" mode="form,tree" colspan="4" height="200">
              </field>
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


Tree view
=========

The RNG that describes the xml for a tree view is stored in
trytond/ir/ui/tree.rng. There is also a RNC in trytond/ir/ui/tree.rnc.

Tree view is used to display records inside a list or a tree.

It is a tree if there is a `field_childs` defined and this tree will
have drag and drop activated if the `field_childs` and the `parent
field` are defined in the view.

The columns of the view are put on the screen from left to right.


XML description
---------------

tree
^^^^

Each tree view must start with this tag.

    * ``string``: The text that will be used as default title for the tab or
      the window.

    * ``on_write``: The name of a function that will be called when a record is
      saved.  The function must have this syntax:

      ``on_write(self, ids)``

    * ``editable``: If it is set to ``top`` or ``bottom``, the list becomes
      editable and the new record will be added on ``top`` or ``bottom`` of the
      list.

    * ``sequence``: The name of the field that is used for sorting.  This field
      must be an integer and it will be updated to match the new sort order
      when the user uses ``Drag and Drop`` on list rows.

    * ``colors``: A PySON string that will be evaluated for each record. A
      string containing the name of the color will be returned.

    * ``fill``: A boolean to specify if the last column must fill the remaining
      free space in the view.

    * ``keyword_open``: A boolean to specify if the client should look for a
      tree_open action on double click instead of switching view.

field
^^^^^

    * ``name``: The name of the field.

    * ``readonly``: Boolean to set the field readonly.

    * ``required``: Boolean to set the field required.

    * ``widget``: The widget that must be used instead of the default one.

    * ``tree_invisible``: Boolean to display or not the column.

    * ``icon``: The name of the field that contains the name of the icon to
      display in the column.

    * ``sum``: A text for the sum widget that will be added on the bottom of
      list with the sum of all the fields in the column.

    * ``width``: Set the width of the column.

Example
-------

.. highlight:: xml

::

  <tree string="Taxes" sequence="sequence">
      <field name="name"/>
      <field name="group"/>
      <field name="type"/>
      <field name="active"/>
      <field name="sequence" tree_invisible="1"/>
  </tree>


Graph view
==========

The RNG that describes the xml for a graph view is stored in
trytond/ir/ui/graph.rng.  There is also a RNC in trytond/ir/ui/graph.rnc.


XML description
---------------

graph
^^^^^

Each graph view must start with this tag.

    * ``type``: ``vbar``, ``hbar``, ``line``, ``pie``

    * ``string``: the name of the graph.

    * ``background``: an hexaecimal value for the color of the
      background.

    * ``color``: the main color.

    * ``legend``: a boolean to specify if the legend must be displayed.

x, y
^^^^

    Describe the field that must be used for axis.  ``x`` must contain
    only one tag ``field`` and ``y`` must at least one but may contain
    many.

field
^^^^^

    * ``name``: the name of the field on the object to use.

    * ``string``: allow to override the string that comes from the
      object.

    * ``key``: can be used to distinguish fields with the same name but
      with different domain.

    * ``domain``: a PySON string which is evaluated with the object value as
      context. If the result is true the field value is added to the graph.

    * ``fill``: defined if the graph shall be filled.

    * ``empty``: defined if the line graph must put a point for missing
      dates.


Example
-------

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
