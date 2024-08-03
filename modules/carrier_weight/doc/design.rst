******
Design
******

The *Carrier Weight Module* extends the following concepts:

.. _model-carrier:

Carrier
=======

When the *Carrier Weight Module* is activated, the *Carrier* gains a new cost
method :guilabel:`Weight` and a new property that list prices per weight.
The price is calculated by finding the first line where the weight is greater
than the weight of the parcel.

.. seealso::

   The `Carrier <carrier:model-carrier>` concept is introduced by the
   :doc:`Carrier Module <carrier:index>`.
