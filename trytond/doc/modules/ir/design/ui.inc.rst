.. _model-ir.ui.menu:

UI Menu
=======

The *Menu* defines the tree structure for the client menu.
Each entry may be linked to one or more `Actions <model-ir.action>` via the
``tree_open`` keyword.
Also, each `User <model-res.user>` can add menu records to their favorites.

.. seealso::

   The Menu entries can be found by opening the main menu item:

      |Administration --> User Interface --> Menu|__

      .. |Administration --> User Interface --> Menu| replace:: :menuselection:`Administration --> User Interface --> Menu`
      __ https://demo.tryton.org/model/ir.ui.menu

.. _model-ir.ui.view:

UI View
=======

The *View* stores the definitions of the different types of view for each
:class:`~trytond.model.Model`.
A *View* can inherit from another *View* to extend its content.

.. seealso::

   The Views can be found by opening the main menu item:

      |Administration --< User Interface --> Views|__

      .. |Administration --< User Interface --> Views| replace:: :menuselection:`Administration --< User Interface --> Views`
      __ https://demo.tryton.org/model/ir.ui.view

Wizards
-------

.. _wizard-ir.ui.view.show:

Show View
^^^^^^^^^

The *Show View* wizard renders the form `View <model-ir.ui.view>`.

.. _model-ir.ui.view_tree_width:

UI View Tree Width
==================

The *View Tree Width* stores the `User <model-res.user>`'s desired column
widths for each `Field <model-ir.model.field>` of the `Model <model-ir.model>`.

.. seealso::

   The View Tree Widths can be found by opening the main menu item:

      |Administration --> User Interface --> View Tree Width|__

      .. |Administration --> User Interface --> View Tree Width| replace:: :menuselection:`Administration --> User Interface --> View Tree Width`
      __ https://demo.tryton.org/model/ir.ui.view_tree_width

.. _model-ir.ui.view_tree_optional:

UI View Tree Optional
=====================

The *View Tree Optional* stores whether a `User <model-res.user>` wants an
optional field to be displayed or not for a `View <model-ir.ui.view>`.

.. seealso::

   The View Tree Optionals can be found by opening the main menu item:

      |Administration --> User Interface --> View Tree Optional|__

      .. |Administration --> User Interface --> View Tree Optional| replace:: :menuselection:`Administration --> User Interface --> View Tree Optional`
      __ https://demo.tryton.org/model/ir.ui.view_tree_optional

.. _model-ir.ui.view_tree_state:

UI View Tree State
==================

The *View Tree State* stores, for each `User <model-res.user>`, the tree view's
expanded and selected nodes for a `Model <model-ir.model>`, `Domain
<topics-domain>` and children.

.. seealso::

   The View Tree States can be found by opening the main menu item:

      |Administration --> User Interface --> Tree State|__

      .. |Administration --> User Interface --> Tree State| replace:: :menuselection:`Administration --> User Interface --> Tree State`
      __ https://demo.tryton.org/model/ir.ui.view_tree_state

.. _model-ir.ui.view_search:

UI View Search
==============

The *View Search* stores the `User's <model-res.user>` saved `Domain
<topics-domain>` for a `Model <model-ir.model>`.

.. seealso::

   The View Searches can be found by opening the main menu item:

      |Administration --> User Interface --> View Search|__

      .. |Administration --> User Interface --> View Search| replace:: :menuselection:`Administration --> User Interface --> View Search`
      __ https://demo.tryton.org/model/ir.ui.view_search

.. _model-ir.ui.icon:

UI Icon
=======

The *Icon* defines the path where a named icon is stored.

.. seealso::

   The Icons can be found by opening the main menu item:

      |Administration --> User Interface --> Icons|__

      .. |Administration --> User Interface --> Icons| replace:: :menuselection:`Administration --> User Interface --> Icons`
      __ https://demo.tryton.org/model/ir.ui.icon
