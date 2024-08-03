******
Design
******

The *Carrier Module* introduces the following concepts:

.. _model-carrier:

Carrier
=======

The *Carrier* defines how the carrier cost is calculated and which service
`Product <product:model-product.product>` to be booked.

.. note::
   The only method to calculate carrier cost provided by default is
   :guilabel:`Product Price`.
   Other modules may add new methods.

.. seealso::

   The *Carriers* can be found by opening the main menu item:

   |Carrier --> Carriers|__

   .. |Carrier --> Carriers| replace:: :menuselection:`Carrier --> Carriers`
   __ https://demo.tryton.org/model/carrier

.. _model-carrier.selection:

Carrier Selection
=================

The *Carrier Selection* defines which carriers are available based on criteria
such as origin and destination `Countries <country:model-country.country>`.

.. seealso::

   The *Carrier Selections* can be found by opening the main menu item:

   |Carrier --> Configuration --> Selection|__

   .. |Carrier --> Configuration --> Selection| replace:: :menuselection:`Carrier --> Configuration --> Selection`
   __ https://demo.tryton.org/model/carrier.selection
