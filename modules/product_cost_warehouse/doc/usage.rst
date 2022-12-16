*****
Usage
*****

.. _Activating cost prices per warehouse:

Activating cost prices per warehouse
====================================

In order to calculate and see `Product <product:concept-product>` cost prices
per warehouse, the :guilabel:`Cost Price Warehouse` option must be checked in
the `Product Configuration <product:model-product.configuration>`.

Any `Storage Locations <stock:model-stock.location>` that are not under a
`Warehouse <stock:concept-stock.location.warehouse>` also need linking to a
cost warehouse.

You must also ensure that the *Scheduled Task* that recalculates the cost
prices is configured to run for each different warehouse.

.. note::

   Once you have activated the cost prices per warehouse if you then want
   to deactivate it you may need to manually run a recalculation of all the
   products' cost prices.

.. _Viewing product cost prices:

Viewing product cost prices
===========================  

With this module activated each `Product's <product:concept-product>` cost
price is shown based on your current `Company <company:model-company.company>`
and `Warehouse <stock:concept-stock.location.warehouse>`.
These can be updated in your user preferences.

.. _Moving stock between warehouses:

Moving stock between warehouses
===============================

If you have checked the :guilabel:`Cost Price Warehouse` option, then to move
stock between different `Warehouses <stock:concept-stock.location.warehouse>`
you must always use a transit `Location <stock:model-stock.location>`.
