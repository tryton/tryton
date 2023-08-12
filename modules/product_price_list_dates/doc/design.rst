******
Design
******

The *Product Price List Dates Module* extends the following concepts:

.. _model-product.price_list:

Price List
==========

When the *Product Price List Dates Modules* is activated, the computation of
price is using the contextual date or today as fallback.
Only lines for which the date is inside the period (or without a period) may be
selected for the computation.

.. _model-product.price_list.cache:

Price List Cache
================

When the *Product Price List Dates Module* and *Product Price List Cache
Module* are activated, the cache is pre-computed for the :ref:`configured range
<config-product_price_list_dates.cache_days>` of date starting from today.
