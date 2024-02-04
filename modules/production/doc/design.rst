******
Design
******

The *Production Module* introduces or extends the following concepts.

.. _model-production.bom:

Bill of Material
================

A :abbr:`*BOM (Bill of Material)*` is a list of `Products
<product:concept-product>` and the quantities needed to manufacture one or
more other products.

.. seealso::

   The BOM can be found using the main menu item:

      |Productions --> Configuration --> BOMs|__

      .. |Productions --> Configuration --> BOMs| replace:: :menuselection:`Productions --> Configuration --> BOMs`
      __ https://demo.tryton.org/model/production.bom

.. _model-concept-product:

Product
=======

When the *Production Module* is activated, products gain some extra properties.
These include a :guilabel:`Producible` checkbox and a list of `BOMs
<model-production.bom>` that it can be produced from.

.. seealso::

   The `Product <product:concept-product>` concept is introduced by the
   :doc:`Product Module <product:index>`.

Wizards
-------

.. _wizard-production.bom.tree.open:

Open BOM Tree
^^^^^^^^^^^^^

The *Open BOM Tree* is a helper wizard used to display the full tree of other
`Products <product:concept-product>` that are required to produce a configured
quantity of the specific product using a `BOM <model-production.bom>`.


.. _model-production:

Production
==========

A *Production* is an order to produce a specific quantity of a `Product
<product:concept-product>`.
A production progresses through different states until it is either done or
cancelled.

Each production contains a list of input `Moves <stock:model-stock.move>` for
the products that are used.
It also has a list of outgoing moves for the products that are created and any
that are scrapped during the production process.

The cost of a production is made up from the cost of all the input moves.
When the production is done, the cost is split proportionally across the output
moves as the unit price.

.. note::

   If the cost of the inputs change after the production is done, a scheduled task
   update the costs of the outputs.

.. _model-stock.location:

Location
========

When the *Production Module* is activated, warehouses gain some extra properties.
These include locations for :guilabel:`Production`, :guilabel:`Production
Picking` and :guilabel:`Production Output` which are used as the default values
when producing products.

.. seealso::

   The `Location <stock:model-stock.location>` concept is introduced by the
   :doc:`Stock Module <stock:index>`.

.. _model-production.configuration:

Configuration
=============

The *Production Configuration* contains settings that are used to configure the
behaviour and default values for production related activities, including the
sequence used to generate `Production <model-production>` numbers.

.. seealso::

   The production configuration can be found using the main menu item:

      |Productions --> Configuration --> Configuration|__

      .. |Productions --> Configuration --> Configuration| replace:: :menuselection:`Productions --> Configuration --> Configuration`
      __ https://demo.tryton.org/model/production.configuration/1
