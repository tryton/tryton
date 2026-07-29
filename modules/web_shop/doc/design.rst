******
Design
******

The *Web Shop Module* introduces some new concepts.

.. _model-web.shop:

Web Shop
========

The *Web Shop* is the main concept provided by the *Web Shop Module*.
It stores the properties of the corresponding shop online such as the `Company
<company:model-company.company>`, the `Currency
<currency:model-currency.currency>`, the `Warehouses
<stock:concept-stock.location.warehouse>` for the stock level and the `Products
<product:concept-product>` sold.

.. seealso::

   Web Shops can be found by opening the main menu item:

      |Sales --> Configuration --> Web Shops|__

      .. |Sales --> Configuration --> Web Shops| replace:: :menuselection:`Sales --> Configuration --> Web Shops`
      __ https://demo.tryton.org/model/web.shop


.. _model-web.user:

Web User
========

When the *Web Shop Module* is activated, the users gain new properties storing
the default invoice and shipment `address <party:model-party.address>`.

.. seealso::

   The `Web User <web_user:model-web.user>` concept is introduced by the
   :doc:`Web User Module <web_user:index>`.

.. _concept-product:

Product
=======

When the *Web Shop Module* is activated, the products gain new properties used
to publish on the web shop.

.. seealso::

   The `Product <product:concept-product>` concept is introduced by the
   :doc:`Product Module <product:index>`.

.. _model-product.category:

Product Category
================

When the *Web Shop Module* is activated, the product categories gain a list of
`web shops <model-web.shop>` on which they must be published.

.. seealso::

   The `Product Category <product:model-product.category>` concept is
   introduced by the :doc:`Product Module <product:index>`.

.. _model-product.attribute:

Product Attribute
=================

When the *Web Shop Module* is activated, the product attributes gain a list of
`web shops <model-web.shop>` on which they must be published.

.. seealso::

   The `Product Attribute <product_attribute:model-product.attribute>` concept
   is introduced by the :doc:`Product Attribute Module
   <product_attribute:index>`.

.. _model-product.image:

Product Image
=============

When the *Web Shop Module* is activated, the product image gains a
:guilabel:`Web Shop` checkbox to indicate if the image must be published.

.. seealso::

   The `Product Image <product_image:model-product.image>` concept is
   introduced by the :doc:`Product Image Module <product_image:index>`.

.. _model-sale.sale:

Sale
====

When the *Web Shop Module* is activated, the sale gains new properties to store
the relations with the web shop.

.. seealso::

   The `Sale <sale:model-sale.sale>` concept is introduced by the :doc:`Sale
   Module <sale:index>`.
