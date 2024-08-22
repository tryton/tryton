.. _model-ir.email:

Email
=====

The *Email* is a :class:`~trytond.ir.resource.ResourceAccessMixin` that stores
a copy of the emails sent from a :class:`~trytond.model.ModelStorage` record.

.. seealso::

   Emails are found by opening the main menu item:

      |Administration --> Models --> Emails|__

      .. |Administration --> Models --> Emails| replace:: :menuselection:`Administration --> Models --> Emails`
      __ https://demo.tryton.org/model/ir.email

   The emails related to a record are found by opening the :guilabel:`Emails
   Archives` menu item from the relate toolbar.

.. _model-ir.email.template:

Email Template
==============

The *Email Template* stores templates per `Model <model-ir.model>` and is used
to fill in the client's Email form.

.. seealso::

   Email Templates are found by opening the main menu item:

      |Administration --> User Interface --> Actions --> Email Templates|__

      .. |Administration --> User Interface --> Actions --> Email Templates| replace:: :menuselection:`Administration --> User Interface --> Actions --> Email Templates`
      __ https://demo.tryton.org/model/ir.email.template
