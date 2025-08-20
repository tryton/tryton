*****
Usage
*****

.. _Configure Shopify Web Shop:

Configure Shopify Web Shop
==========================

First you must create a new `custom app
<https://help.shopify.com/en/manual/apps/app-types>`_ for your Shopify store
with, as a minimum, the :guilabel:`Admin API access scopes`:

   * :guilabel:`Assigned fulfillment`: ``write_assigned_fulfillment_orders``

   * :guilabel:`Fulfillment services`: ``write_fulfillments``

   * :guilabel:`Inventory`: ``write_inventory``

   * :guilabel:`Locations`: ``read_locations``

   * :guilabel:`Merchant-managed fulfillment orders`:
     ``write_merchant_managed_fulfillment_orders``

   * :guilabel:`Orders`: ``write_orders``

   * :guilabel:`Product listings`: ``write_product_listings``

   * :guilabel:`Products`: ``write_products``

You also need to copy the :guilabel:`Admin API access token` that is generated
when installing the app.

When setting the :doc:`Web Shop <web_shop:index>`'s type to  "Shopify", you
must fill in the :guilabel:`Shop URL` (e.g.
``https://<store-name>.myshopify.com``), the :guilabel:`Access Token` with the
copied one and select the :guilabel:`Version`.

.. note::

   At least one `Payment Journal <model-web.shop.shopify_payment_journal>` is
   needed to book the transactions.

Different scheduled tasks are responsible for uploading products and
inventories and fetching and updating orders as `Sales <sale:model-sale.sale>`.

You can also register a :abbr:`JSON (JavaScript Object Notation)` `webhook
<https://shopify.dev/docs/apps/build/webhooks>`_ from the
:guilabel:`Notifications` settings for each order event to get updates when
they happen.

.. _Setup Shopify Variants:

Setup Shopify Variants
======================

To create variants of a product in Shopify, you need to set an `Attribute
Set <product_attribute:model-product.attribute.set>` on the `Product Template
<product:model-product.template>`.
This *Attribute Set* must have at least one of the three :guilabel:`Shopify
Options` selected with an `Attribute
<product_attribute:model-product.attribute>`.

.. note::

   For each variant of a product, the value of the :guilabel:`Shopify Options`
   attributes must be unique.

.. _Admin links:

Admin Links
===========

The module provides links that offer direct access to the corresponding Tryton
record based on the Shopify identifier.
You can use these links to create an `admin link extension
<https://shopify.dev/docs/apps/build/admin/admin-links>`_.

   - ``GET`` ``/<database_name>/web_shop_shopify/products/<product id>``

   - ``GET`` ``/<database_name>/web_shop_shopify/products/<product id>/variants/<variant id>``

   - ``GET`` ``/<database_name>/web_shop_shopify/customers/<customer id>``

   - ``GET`` ``/<database_name>/web_shop_shopify/orders/<order id>``
