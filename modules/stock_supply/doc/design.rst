******
Design
******

The *Stock Supply Module* introduces or extends the following concepts:

.. _model-stock.location:

Location
========

When the *Stock Supply Module* is activated, the storage location gains new
properties that define the default provisioning and overflowing locations for
that particular location.

.. seealso::

   The `Stock Location <stock:model-stock.location>` concept is introduced by
   the :doc:`Stock Module <stock:index>`.

.. _model-stock.order_point:

Order Point
===========

The *Order Point* defines the replenishment policy for a product on a specific
location.
It established the quantity threshold that determines when stock should be
replenished or reduced in order to maintain desired inventory level.

The desired inventory level is defined as follows:

   * :guilabel:`Minimal Quantity`: the level below which stock must be
     replenished.

   * :guilabel:`Target Quantity`: the level to which stock should be restored
     after replenishment.

   * :guilabel:`Maximal Quantity`: the level above which excess stock should be
     moved.

There are two types of order point depending on how the replenishment is
handled:

Internal
--------

An *Internal* order point is defined for a storage location, using `internal
shipments <model-stock.shipment.internal>` as the replenishment method.
When stock falls below the minimum quantity, the system transfers stock from
the :guilabel:`Provisioning Location`.
When the stock rises above the maximum quantity, the system transfers the
excess stock to :guilabel:`Overflowing Location`.

Purchase
--------

A *Purchase* order point is defined on a `warehouse location
<stock:concept-stock.location.warehouse>`.
When the stock level falls below the minimum quantity, a `purchase request
<purchase_request:model-purchase.request>` is generated to replenish the
product from the supplier.

.. seealso::

   The list of *Order Points* can be found by opening the main menu item:

      |Inventory & Stock --> Order Points|__

      .. |Inventory & Stock --> Order Points| replace:: :menuselection:`Inventory & Stock --> Order Points`
      __ https://demo.tryton.org/model/stock.order_point

.. _model-purchase.configuration:

Purchase Configuration
======================

When the *Stock Supply Module* is activated, the purchase configuration gains a
new property that defines the replenishment period for stock levels for
`purchases <purchase:model-purchase.purchase>`.

.. seealso::

   The `Purchase Configuration <purchase:model-purchase.configuration>` concept
   is introduced by the :doc:`Purchase Module <purchase:index>`.

.. _wizard-stock.supply:

Supply
======

The *Supply* wizard automates product replenishment across `warehouses
<stock:concept-stock.location.warehouse>` according to `Order Points
<model-stock.order_point>`.
It calculates the stock level for each `product
<product:model-product.product>` in every warehouses every day over the
`supplier period <model-purchase.configuration>` for purchase and over the
`lead time <stock:model-stock.location.lead_time>` for internal shipment.

.. seealso::

    The *Supply* wizard can be launched from the main menu:

    |Inventory & Stock --> Supply Stock|__

    .. |Inventory & Stock --> Supply Stock| replace:: :menuselection:`Inventory & Stock --> Supply Stock`
    __ https://demo.tryton.org/wizard/stock.supply
