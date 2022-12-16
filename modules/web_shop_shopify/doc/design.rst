******
Design
******

The *Web Shop Shopify Module* introduces some new concepts.

.. _model-web.shop.shopify_identifier

Shopify Identifier
==================

A *Shopify Identifier* stores the Shopify ID for records from other models for
each different `Web Shop <web_shop:model-web.shop>`.

.. seealso::

   Identifiers are found by opening the main menu item:

      |Administration --> Models --> Shopify Identifiers|__

      .. |Administration --> Models --> Shopify Identifiers| replace:: :menuselection:`Administration --> Models --> Shopify Identifiers`
      __ https://demo.tryton.org/model/web.shop.shopify_identifier

.. model-web.shop.shopify_payment_journal

Shopify Payment Journal
=======================

The *Shopify Payment Journal* stores the rules which are used to determine on
which `Payment Journal <account_payment:model-account.payment.journal>` the
transactions are entered.

.. model-stock.shipment.shopify_identifier

Shopify Shipment Identifier
===========================

The *Shopify Shipment Identifier* concept stores the Shopify ID for the shipments
for each `Sale <sale:model-sale.sale>`.

.. seealso::

   Identifiers are found by opening the main menu item:

      |Administration --> Models --> Shopify Identifiers --> Shipment Identifiers|__

      .. |Administration --> Models --> Shopify Identifiers --> Shipment Identifiers| replace:: :menuselection:`Administration --> Models --> Shopify Identifiers --> Shipment Identifiers`
      __ https://demo.tryton.org/model/stock.shipment.shopify_identifier


.. model-web.shop.shopify_inventory_item

Shopify Inventory Item
======================

The *Shopify Inventory Item* concept manages the Shopify inventory item of each
`Varient <product:model-product.product>`.
