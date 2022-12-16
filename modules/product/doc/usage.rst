*****
Usage
*****

The items found under the [:menuselection:`Product`] main menu item allow you
to view and manage the products on your system.

.. _Using product templates and variants:

Using product templates and variants
====================================

Tryton makes it easy to create `Products <model-product.template>` which have
one or more slightly different `Variants <model-product.product>`.

A simple example of where you could use this is in a company that supplies
clothes.
Each type of shirt may come in a range of different sizes, but most of the
properties of the shirt, such as the name, unit of measurement, categories,
and so on, would be the same.
So in this case you would create a single *Product* to represent the shirt,
and a *Variant* for each of the different sizes.
Structuring your products like this can help you manage and update them.

.. tip::

   You may find that your products are not suited to being structured in this
   way.
   If so, don't worry, when you create a new *Product* from the
   [:menuselection:`Products --> Products`] menu item a single variant is
   automatically created for you and displayed as part of the product.

.. _Categorising products:

Categorising products
=====================

It can be a good idea to organise your `Products <concept-product>` into
groups.
This makes it much easier to find and manage them effectively, especially if
you have a lot of products on your system.

The product `Categories <model-product.category>` are designed for this
purpose.
You can create categories with any name you want, and then add the appropriate
categories to each product.
Each product can belong to as many, or as few, categories as required.
The categories can also be organised into a
structure, with each category having a parent category and some subcategories.
This can help you classify your products more finely.

For example, a clothes supplier may use these categories::

   Accessories
   Clothes
      Shirts
         Short sleeves
         Long sleeves
      Jumpers
   Range
      Spring Summer
      Autumn Winter
      Christmas

Based on these categories, you may decide that a particular lightweight shirt
belongs in the ``Clothes / Shirts / Short sleeves`` and
``Range / Spring Summer`` categories.

.. tip::

   To get a list of all the products in a category first open the
   [:menuselection:`Products --> Categories`] menu item.
   Then when you open one of the categories listed here you will get a list
   of all the products in that category.
