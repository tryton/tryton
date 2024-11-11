.. _model-ir.model:

Model
=====

The *Model* stores a record of each subclass of :class:`~trytond.model.Model`
that is registered in the :class:`~trytond.pool.Pool`.

A model is composed of `Fields <model-ir.model.field>` that represents each
:class:`~trytond.model.fields.Field` it contains.

The administrator can enable global search for records of the model by checking
the :guilabel:`Global Search` box.

.. seealso::

   Models are found by opening the main menu item:

      |Administration --> Models --> Models|__

      .. |Administration --> Models --> Models| replace:: :menuselection:`Administration --> Models --> Models`
      __ https://demo.tryton.org/model/ir.model

Reports
-------

.. _report-ir.model.workflow_graph:

Workflow Graph
--------------

The *Workflow Graph* prints a `state diagram
<https://en.wikipedia.org/wiki/State_diagram>`_ for each selected
:class:`~trytond.model.Workflow` *Model*.

Wizards
-------

.. _wizard-ir.model.print_model_graph:

Graph
^^^^^

The *Graph* wizard prints an `object diagram
<https://en.wikipedia.org/wiki/Object_diagram>`_ that shows the relationships
between the selected *Models* down to the specified depth.

.. _model-ir.model.field:

Model Field
===========

The *Model Field* keeps a record for each subclass of
:class:`~trytond.model.fields.Field` that a `Model <model-ir.model>` contains.

.. seealso::

   Model Fields are found by opening the main menu item:

      |Administration --> Models --> Models --> Fields|__

      .. |Administration --> Models --> Models --> Fields| replace:: :menuselection:`Administration --> Models --> Models --> Fields`
      __ https://demo.tryton.org/model/ir.model.field

.. _model-ir.model.access:

Model Access
============

The *Model Access* defines the `access rights <topics-access_rights>` to
`Models <model-ir.model>` for each `Group <model-res.group>`.

.. seealso::

   Models Access are found by opening the main menu item:

      |Administration --> Models --> Models Access|__

      .. |Administration --> Models --> Models Access| replace:: :menuselection:`Administration --> Models --> Models Access`
      __ https://demo.tryton.org/model/ir.model.access

.. _model-ir.model.field.access:

Model Field Access
===================

The *Model Field Access* defines the `access rights <topics-access_rights>` to
`Model Fields <model-ir.model.field>` for each `group <model-res.group>`.

.. seealso::

   Model Fields Access are found by opening the main menu item:

      |Administration --> Models --> Models Access --> Fields Access|__

      .. |Administration --> Models --> Models Access --> Fields Access| replace:: :menuselection:`Administration --> Models --> Models Access --> Fields Access`
      __ https://demo.tryton.org/model/ir.model.field.access

.. _model-ir.model.button:

Model Button
============

The *Model Button* stores the buttons defined in the `Models <model-ir.model>`.
It also contains a list of `Groups <model-res.group>` that have `access
<topics-access_rights>` to the button and a list of rules that must be
satisfied to trigger the button's action.

.. seealso::

   Model Buttons are found by opening the main menu item:

      |Administration --> Models --> Models Access --> Buttons|__

      .. |Administration --> Models --> Models Access --> Buttons| replace:: :menuselection:`Administration --> Models --> Models Access --> Buttons`
      __ https://demo.tryton.org/model/ir.model.button

.. _model-ir.model.data:

Model Data
==========

The *Model Data* keeps track of the :class:`~trytond.model.ModelStorage`
records created by modules via `XML files <topics-modules-tryton-cfg>`.

.. _model-ir.model.log:

Model Log
=========

The *Model Log* records events such as modification, suppression, click, launch
and transition that happened to a :class:`~trytond.model.ModelStorage` record.

.. seealso::

   Model Logs are found by opening the main menu item:

      |Administration --> Models --> Models --> Logs|__

      .. |Administration --> Models --> Models --> Logs| replace:: :menuselection:`Administration --> Models --> Models --> Logs`
      __ https://demo.tryton.org/model/ir.model.log

   The logs related to a record are found by opening the :guilabel:`View
   Logs...` menu item of the toolbar.
