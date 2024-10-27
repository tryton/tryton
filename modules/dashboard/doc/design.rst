******
Design
******

The *Dashboard Module* introduces or extends the following concepts:

.. _model-dashboard.action:

Dashboard Action
================

The *Dashboard Action* links a `Window Action
<trytond:model-ir.action.act_window>` to a `User <trytond:model-res.user>`.

.. note::
   To be used a window action must have the :guilabel:`Usage` set to
   ``dashboard``.

.. _model-res.user:

User
====

When the *Dashboard Module* is activated, the *User* gains new properties to
allow them to define the layout and the actions to be displayed by the
dashboard.

.. seealso::

   The `User <trytond:model-res.user>` concept is introduced by the
   :ref:`Resource Module <trytond:res>`.
