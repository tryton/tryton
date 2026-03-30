******
Design
******

The *Production Routing Module* introduces or extends the following concepts.

.. _model-production.routing:

Routing
=======

A *Routing* specifies the operational steps involved in a `Production
<production:model-production>` process and the order in which in they occur.
Routings can be linked to multiple `Bill of Materials
<production:model-production.bom>`.

.. seealso::

   The Routings can be found using the main menu item:

      |Productions --> Configuration --> Routings|__

      .. |Productions --> Configuration --> Routings| replace:: :menuselection:`Productions --> Configuration --> Routings`
      __ https://demo.tryton.org/model/production.routing

.. _model-production.routing.operation:

Operation
=========

An *Operation* is a general production activity.

.. seealso::

   The *Operations* can be found using the main menu item:

      |Productions --> Configuration --> Routings --> Operations|__

      .. |Productions --> Configuration --> Routings --> Operations| replace:: :menuselection:`Productions --> Configuration --> Routings --> Operations`
      __ https://demo.tryton.org/model/production.routing

.. _concept-product:

Product
=======

When the *Production Routing Module* is activated, products gain some extra
properties.
A `Routing <model-production.routing>` can be specified for each `BOMs
<production:model-production.bom>` listed.
A production lead times can also be defined per `Routing
<model-production.routing>`.

.. seealso::

   The `Product <production:concept-product>` concept is extended from the
   :doc:`Production Module <production:index>`.

.. _model-production:

Production
==========

When the *Production Routing Module* is activated, productions gain some extra
properties such as the `Routing <model-production.routing>` which is used to
adapt the lead time.

.. seealso::

   The `Production <production:model-production>` concept is introduced by the
   :doc:`Production Module <production:index>`.
