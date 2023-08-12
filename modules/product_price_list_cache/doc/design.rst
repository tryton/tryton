******
Design
******

The *Product Price List Cache Module* introduces the following concepts:

.. _model-product.price_list.cache:

Price List Cache
================

The *Price List Cache* stores for each product and price list the list of
couple quantity and price.
The cache is filled by a *Scheduled Task* which delete and pre-compute prices
every day.
