******
Design
******

The *Authentication SMS Module* extends the following concepts:

.. _model-res.user:

User
====

When *Authentication SMS Module* is activated, the *User* gains a new property
for the user's :guilabel:`Mobile` number.

.. note::
   The :guilabel:`Mobile` is required in order to send the user the code they
   need to authenticate with when using the ``sms`` method.

.. seealso::

   The `User <trytond:model-res.user>` concept is introduced by the `Resource
   Module <trytond:res>`.
