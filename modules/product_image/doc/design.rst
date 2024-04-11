******
Design
******

The *Product Image module* introduces some new concepts.

.. _model-product.image:

Product Image
=============

The *Product Image* concept store images for a `Product
<product:concept-product>`.
The images are stored as `JPEGs <https://en.wikipedia.org/wiki/JPEG>`_ format
and with a maximal horizontal and vertical size of `image_size_max
<config-product-image_size_max>`.


.. _model-product.category.image:

Category Image
==============

The *Category Image* concept stores images for a `Category
<product:model-product.category>` using the same constraint as `Product Image
<model-product.image>`.
