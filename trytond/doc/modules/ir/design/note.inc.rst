.. _model-ir.note:

Note
====

*Note* is a :class:`~trytond.ir.resource.ResourceMixin` that stores `User
<model-res.user>`'s messages associated with any
:class:`~trytond.model.ModelStorage` record.
The *Note* keeps track of who has read each message.

.. seealso::

   Notes are found by opening the main menu item:

      |Administration --> Models --> Notes|__

      .. |Administration --> Models --> Notes| replace:: :menuselection:`Administration --> Models --> Notes`
      __ https://demo.tryton.org/model/ir.note

   The notes related to a record are found by opening the :guilabel:`Note` menu
   item of the toolbar.
