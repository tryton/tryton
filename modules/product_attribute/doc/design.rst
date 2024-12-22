******
Design
******

The *Product Attribute Module* introduces the following concepts:


.. _model-product.template:

Product Template
================

When the *Product Attribute Module* is activated, product templates gain some
extra properties.
These include an `Attribute Set <model-product.attribute.set>` which defines
the `Attributes <model-product.attribute>` available for its variants.

.. seealso::

   The `Product Template <product:model-product.template>` concept is
   introduced by the :doc:`Product Module <product:index>`.

.. _model-product.product:

Product Variant
===============

When the *Product Attribute Module* is activated, product variants gain some
extra properties.
These include a list of `Attribute <model-product.attribute>` values and a name
calculated using these values.

.. seealso::

   The `Product Variant <product:model-product.product>` concept is
   introduced by the :doc:`Product Module <product:index>`.

.. _model-product.attribute:

Product Attribute
=================

An *Attribute* is a :class:`~trytond:trytond.model.DictSchemaMixin` that
defines a property for a `Product Variant <product:model-product.product>` such
as a color, a dimension and so on.

.. seealso::

   The *Attributes* can be found by opening the main menu item:

      |Products --> Configuration --> Attributes|__

      .. |Products --> Configuration --> Attributes| replace:: :menuselection:`Products --> Configuration --> Attributes`
      __ https://demo.tryton.org/model/product.attribute

.. _model-product.attribute.set:

Product Attribute Set
=====================

The *Attribute Set* groups `Product Attributes <model-product.attribute>`
together.

.. seealso::

   The *Attribute Sets* can be found by opening the main menu item:

      |Products --> Configuration --> Attribute Sets|__

      .. |Products --> Configuration --> Attribute Sets| replace:: :menuselection:`Products --> Configuration --> Attribute Sets`
      __ https://demo.tryton.org/model/product.attribute.set
