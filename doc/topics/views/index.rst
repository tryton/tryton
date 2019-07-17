.. _topics-views:

=====
Views
=====

The views are used to display records of an :class:`ModelView
<trytond.model.ModelView>` to the user.

In Tryton, :class:`ModelView <trytond.model.ModelView>` can have several views.
An `action` opens a window and defines which view to show.

The views are built from XML that is stored in the `view` directory of the
module or in the databases thanks to the model ir.ui.view.

So generally, they are defined in xml files with this kind of xml where name is
the name of the XML file in the `view` directory:

.. highlight:: xml

::

  <record model="ir.ui.view" id="view_id">
      <field name="model">model name</field>
      <field name="type">type name</field>
      <!--field name="inherit" ref="inherit_view_id"/-->
      <!--field name="field_childs">field name</field-->
      <field name="name">view_name</field>
  </record>


There is three types of views:

    * Form

    * Tree

    * Graph

    * Board

    * Calendar

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
      at the beginning of the next row.


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

    .. _common-attributes-col:

    * ``col``: The number of columns the container must have.

      A negative value (or zero) will remove the constraint on the number of
      columns.

      The default value is 4.

    .. _common-attributes-states:

    * ``states``: A string of :ref:`PYSON statement <topics-pyson>` that will
      be evaluated with the values of the current record.

      It must return a dictionary where keys can be:

        * ``invisible``: If true, the widget will be hidden.

        * ``required``: If true, the field will be required.

        * ``readonly``: If true, the field will be readonly.

        * ``icon``: Only for button, it must return the icon name to use or
          False.

        * ``pre_validate``: Only for button, it contains a domain to apply
          on the record before calling the button.

        * ``depends``: Only for button, it must return the list of field on
          which the button depends.

    .. _common-attributes-help:

    * ``help``: The string that will be displayed when the cursor hovers over
      the widget.

    .. _common-attributes-pre_validate:

    * ``pre_validate``: A boolean only for fields
      :class:`trytond.model.fields.One2Many` to specify if the client must
      pre-validate the records using
      :meth:`trytond.model.Model.pre_validate`.

    .. _common-attributes-completion:

    * ``completion``: A boolean only for fields
      :class:`trytond.model.fields.Many2One`,
      :class:`trytond.model.fields.Many2Many` and
      :class:`trytond.model.fields.One2Many` to specifiy if the client must
      auto-complete the field. The default value is True.

    .. _common-attributes-factor:

    * ``factor``: A factor to apply on fields
      :class:`trytond.model.fields.Integer`,
      :class:`trytond.model.fields.Float` and
      :class:`trytond.model.fields.Numeric` to display on the widget. The
      default value is 1.


form
^^^^

Each form view must start with this tag.

    .. _form-attributes-on_write:

    * ``on_write``: The name of a method on the Model of the view that will be
      called when a record is saved.  The method must return a list of record
      ids that the client must reload if they are already loaded.  The function
      must have this syntax:

      ``on_write(self, ids)``

      .. note::
        The method must be registered in :attr:`trytond.model.Model.__rpc__`.
      ..

    * ``col``: see in common-attributes-col_.

    * ``cursor``: The name of the field that must have the cursor by default.

label
^^^^^

Display static string.

    * ``string``: The string that will be displayed in the label.

    * ``name``: The name of the field whose description will be used for
      string. Except if ``string`` is set, it will use this value and the value
      of the field if ``string`` is empty.

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

    * ``string``: The string that will be displayed for the widget.

    * ``widget``: The widget that must be used instead of the default one.

    * ``help``: The string that will be displayed when the cursor stays over the
      widget.

    * ``width``: The minimum width the widget should request, or -1 to unset.

    * ``height``: The minimum height the widget should request, or -1 to unset.

    * ``readonly``: Boolean to set the field readonly.

    * ``mode``: Only for One2Many fields: it is a comma separated list, that
      specifies the order of the view used to display the relation. (Example:
      ``tree,form``)

    * ``view_ids``: A comma separated list that specifies the view ids used to
      display the relation. For Many2One and Many2Many, the order should always
      be tree then form.

    * ``product``: Only for One2Many fields, a comma separated list of target
      field name used to create records from the cartesian product.

    * ``completion``: Only for Many2One fields, it is a boolean to set the
      completion of the field.

    * ``invisible``: The field will not be displayed, but it will fill cells in
      the table.

    * ``filename_visible``: Only for Binary fields, boolean that enables the
      display of the filename.

    * ``toolbar``: Only for Rich Text widget, boolean that enables the
      display of the Rich Text toolbar. The default value is 1.

    * ``yexpand``: see in common-attributes-yexpand_.

    * ``yfill``: see in common-attributes-yfill_.

    * ``xexpand``: see in common-attributes-xexpand_.

    * ``xfill``: see in common-attributes-xfill_.

    * ``colspan``: see in common-attributes-colspan_.

    * ``help``: see in common-attributes-help_.

    * ``pre_validate``: see in common-attributes-pre_validate_.

    * ``completion``: see in common-attributes-completion_.

    * ``factor``: see in common-attributes-factor_.

image
^^^^^

Display an image.

    * ``name``: the image name or the field name which contains the image name.
      The image name must be the name of a record of `ir.ui.icon`.

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


.. _form-button:

button
^^^^^^

Display a button.

    * ``name``: The name of the function that will be called. The function must
      have this syntax:

        ``button(cls, records)``

      The function may return an `ir.action` id or one of those client side
      action keywords:

.. _topics-views-client-actions:

        * ``new``: to create a new record
        * ``delete``: to delete the selected records
        * ``remove``: to remove the record if it has a parent
        * ``copy``: to copy the selected records
        * ``next``: to go to the next record
        * ``previous``: to go to the previous record
        * ``close``: to close the current tab
        * ``switch <view type> [<view id>]``: to switch the view
        * ``reload``: to reload the current tab
        * ``reload context``: to reload user context
        * ``reload menu``: to reload menu

    * ``icon``

    * ``confirm``: A text that will be displayed in a confirmation popup when
      the button is clicked.

    * ``colspan``: see in common-attributes-colspan_.

    * ``states``: see in common-attributes-states_.

    * ``help``: see in common-attributes-help_.

    * ``keyword``: specify where will the button be displayed in the client
      toolbar. The valid values are the keywords starting with `form_` from
      :ref:`Actions <topics-actions>` without the `form_` part.


.. warning::
    The button should be registered on ``ir.model.button`` where the default
    value of the ``string``, ``confirm`` and ``help`` attributes can be can be
    defined.


notebook
^^^^^^^^

It adds a notebook widget which can contain page tags.

    * ``colspan``: see in common-attributes-colspan_.

    * ``states``: see in common-attributes-states_.

page
^^^^

Define a new tab inside a notebook.

    * ``string``: The string that will be displayed in the tab.

    * ``angle``: The angle in degrees between the baseline of the label and the
      horizontal, measured counterclockwise.

    * ``col``: see in common-attributes-col_.

    * ``id``: see in common-attributes-id_.

    * ``states``: see in common-attributes-states_.

    * Requires that either ``id`` or ``name`` is defined.

group
^^^^^

Create a sub-table in a cell.

    * ``string``: If set a frame will be drawn around the field with a label
      containing the string. Otherwise, the frame will be invisible.

    * ``rowspan``: The number of rows the group spans in the table.

    * ``col``: see in common-attributes-col_.

    * ``expandable``: If this attribute is present the content of the group
      will be expandable by the user to reveal its content. A value of "1"
      means that the group will start expanded, a value of "0" means
      that the group will start unexpanded. There is no default value.

    * ``homogeneous``: If True all the tables cells are the same size.

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

child
^^^^^

Contains the childs of a hpaned or vpaned.

.. _example_form_view:

Example
-------

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

    * ``on_write``: see form-attributes-on_write_.

    * ``editable``: If it is set to ``top`` or ``bottom``, the list becomes
      editable and the new record will be added on ``top`` or ``bottom`` of the
      list.

    * ``sequence``: The name of the field that is used for sorting.  This field
      must be an integer and it will be updated to match the new sort order
      when the user uses ``Drag and Drop`` on list rows.

    * ``keyword_open``: A boolean to specify if the client should look for a
      tree_open action on double click instead of switching view.

    * ``tree_state``: A boolean to specify if the client should save the state
      of the tree.

field
^^^^^

    * ``name``: The name of the field.

    * ``readonly``: Boolean to set the field readonly.

    * ``widget``: The widget that must be used instead of the default one.

    * ``tree_invisible``: A string of :ref:`PYSON statement <topics-pyson>`
      that will be evaluated as boolean with the context of the view to display
      or not the column.

    * ``icon``: The name of the field that contains the name of the icon to
      display in the column.

    * ``sum``: A text for the sum widget that will be added on the bottom of
      list with the sum of all the fields in the column.

    * ``width``: Set the width of the column.

    * ``expand``: Boolean to specify if the column should be expanded to take
      available extra space in the view. This space is shared equally among all
      columns that have their "expand" property set to True. Resize don't work
      if this option is enabled.

    * ``pre_validate``: see in common-attributes-pre_validate_.

    * ``completion``: see in common-attributes-completion_.

    * ``factor``: see in common-attributes-factor_.

prefix or suffix
^^^^^^^^^^^^^^^^

A ``field`` could contain one or many ``prefix`` or ``suffix`` that will be
diplayed in the same column.

    * ``string``: The text that will be displayed.

    * ``name``: The name of the field whose value will be displayed.

    * ``icon``: The name of the field that contains the name of the icon to
      display or the name of the icon.

button
^^^^^^

Same as in form-button_.

Example
-------

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

button
^^^^^^

Display a button.

    * ``string``: The string that will be displayed inside the button.

    * ``name``: The name of the function that will be called. The function must
      have this syntax:

        ``button(cls, records)``

    * ``confirm``: A text that will be displayed in a confirmation popup when
      the button is clicked.

    * ``help``: see in common-attributes-help_

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

    * ``color``: the color of the field.

    * ``interpolation``: defined how the line graph must interpolate points.
      The default is ``linear``.

        * ``constant-center``: use the value of the nearest point, see
          `Nearest-neighbor interpolation`_

        * ``constant-left``: use the value of the nearest left point.

        * ``constant-right``: use the value of the nearest right point.

        * ``linear``: see `linear interpolation`_

.. _`Nearest-neighbor interpolation`:
    http://en.wikipedia.org/wiki/Nearest-neighbor_interpolation
.. _`linear interpolation`: http://en.wikipedia.org/wiki/Linear_interpolation


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


Board view
==========

The RNG that describes the xml for a board view is stored in
trytond/ir/ui/board.rng.  There is also a RNC in trytond/ir/ui/graph.rnc.

Board view is used to display multiple views at once.

Elements are put on the screen followin the same rules as for ``Form`` view.

The views can be updated by the selection of records on an other view inside
the same board by using :class:`~trytond.pyson.Eval()` on the action id of the
other view in the domain.


XML description
---------------

board
^^^^^

Each board view must start with this tag.

    * ``col``: see in common-attributes-col_.

image
^^^^^

Same as in ``Form`` view.

separator
^^^^^^^^^

Same as in ``Form`` view.

label
^^^^^

Same as in ``Form`` view.

newline
^^^^^^^

Same as in ``Form`` view.

notebook
^^^^^^^^

Same as in ``Form`` view.

page
^^^^

Same as in ``Form`` view.

group
^^^^^

Same as in ``Form`` view.

hpaned, vpaned
^^^^^^^^^^^^^^

Same as in ``Form`` view.

child
^^^^^

Same as in ``Form`` view.

action
^^^^^^

    * ``name``: The id of the action window.

    * ``colspan``: see in common-attributes-colspan_.

Calendar view
=============

The RNG that describes the xml for a calendar view is stored in
trytond/ir/ui/calendar.rng. There is also a RNC in trytond/ir/ui/calendar.rnc.

Calendar view is use to display records as events on a calendar based on a
`dtstart` and optionally a `dtend`.

XML description
---------------

calendar
^^^^^^^^

Each calendar view must start with this tag.

    * ``dtstart``: The name of the field that contains the start date.

    * ``dtend``: The name of the field that contains the end date.

    * ``mode``: An optional name for the view that will be used first.
      Available views are: `week` and `month`. The default value is `month`.

    * ``color``: An optional field name that contains the text color for the
      event. The default value is `black`.

    * ``background_color``: An optional field name that contains the background
      color for the event. The default value is `lightblue`.

field
^^^^^

    * ``name``: The name of the field.

Example
-------

.. highlight:: xml

::

  <calendar dtstart="planned_date">
      <field name="code"/>
      <field name="product"/>
      <field name="reference"/>
  </calendar>
