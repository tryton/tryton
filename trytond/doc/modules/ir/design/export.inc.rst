.. _model-ir.export:

Export
======

The *Export* stores the saved exports for each `User <model-res.user>`.
An export is composed of a list of :class:`~trytond.model.fields.Field` names.
When an *Export* is associated with a `Group <model-res.group>`, it becomes
available for all the *Users* of that *Group*.

.. seealso::

   The exports can be found by opening the main menu item:

      |Administration --> Models --> Exports|__

      .. |Administration --> Models --> Exports| replace:: :menuselection:`Administration --> Models --> Exports`
      __ https://demo.tryton.org/model/ir.export
