*****
Usage
*****

.. _Configure Shopify Web Shop:

Configure Shopify Web Shop
==========================

First you must create a new `custom app
<https://help.shopify.com/en/manual/apps/app-types#custom-apps>`_ for your
Shopify store with, as a minimum, the following permissions:

   * Fulfillment services: Read and write

   * Inventory: Read and write

   * Orders: Read and write

   * Product listings: Read and write

   * Products: Read and write

   * Assigned fulfillment: Read and write

   * Merchant-managed fulfillment orders: Read and write

You also need to copy the password that is generated.

When setting the :doc:`Web Shop <web_shop:index>`'s type to  "Shopify", you
must fill in the "Shop URL" (e.g. ``https://<store-name>.myshopify.com``) and
the "Password" with the copied one.

.. note::

   At least one `Payment Journal <model-web.shop.shopify_payment_journal>` is
   needed to book the transactions.

Different scheduled tasks are responsible for uploading products and
inventories and fetching and updating orders as `Sales <sale:model-sale.sale>`.

You can also register a `webhook <https://shopify.dev/apps/webhooks>`_ for each
order event to get updates when they happen.
