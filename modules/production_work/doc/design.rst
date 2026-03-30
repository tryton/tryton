******
Design
******

The *Production Work Module* introduces or extends the following concepts.

.. _model-production.work.center:

Work Center
===========

A *Work Center* represents a specific area or a machine in which a particular
set of `Operations <production_routing:model-production.routing.operation>` is
performed.
Work centers can be organized into a tree structure representing a production
chain, with each work center linked to a `Category
<model-production.work.center.category>`.
The cost of each work center can be defined using different methods, such as
per cycle or per hour.

.. seealso::

   The *Work Centers* can be accessed via the main menu:

      |Production --> Configuration --> Work Centers|__

      .. |Production --> Configuration --> Work Centers| replace:: :menuselection:`Production --> Configuration --> Work Centers`
      __ https://demo.tryton.org/model/production.work.center

.. _model-production.work.center.category:

Work Center Category
====================

The *Work Center Category* concept provides a way of grouping `Work Centers
<model-production.work.center>`.

.. seealso::

   The list of *Work Center Categories* can be accessed via the main menu item:

      |Production --> Configuration --> Work Center Categories|__

      .. |Production --> Configuration --> Work Center Categories| replace:: :menuselection:`Production --> Configuration --> Work Center Categories`
      __ https://demo.tryton.org/model/production.work.center.category

.. _model-production.work:

Work
====

A *Work* represents an `Operation
<production_routing:model-production.routing.operation>` assigned to a `Work
Center <model-production.work.center>` as part of a `Production order
<production:model-production>`.

Each work, at any time, can ben in one of several different states.
A work progresses through these states until it is done.
During this process, the number and the duration of each cycle are recorded to
calculate the total cost of the work.

.. seealso::

   The list of *Works* can be accessed via the main menu:

      |Production --> Works|__

      .. |Production --> Works| replace:: :menuselection:`Production --> Works`
      __ https://demo.tryton.org/model/production.work

.. _model-production.routing.operation:

Operation
=========

When the *Production Work Module* is activated, the operation can be linked to
a `Work Center Category <model-production.work.center.category>` which
determines which `Work Centers <model-production.work.center>` can support the
operation.

.. seealso::

   The `Operation <production_routing:model-production.routing.operation>`
   concept is introduced by the :doc:`Production Routing Module
   <production_routing:index>`.

.. _model-production:

Production
==========

When the *Production Work Module* is activated, the production gains new
properties such as the main `Work Center <model-production.work.center>` and
the list of `Works <model-production.work>` that are defined by default from
the `Routing <production_routing:model-production.routing>`.

.. seealso::

   The `Production <production:model-production>` concept is introduced by the
   :doc:`Production Module <production:index>`.
