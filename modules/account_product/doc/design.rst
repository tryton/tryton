******
Design
******

The *Account Product Module* mainly extends existing accounting and product
concepts.

.. _concept-product:

Product
=======

The *Product* concept is extended with a set of methods that allow access to
the product's accounting related properties.

Many of these properties are set in the product's accounting category.
The accounting category is a special type of
`Product Category <model-product.category>`.
Unlike standard product categories, each product can only have a single
accounting category.

.. seealso::

   The `Product <product:concept-product>` concept is introduced by the
   :doc:`Product Module <product:index>`.

.. _model-product.category:

Product Category
================

The *Account Product Module* allows some *Product Categories* to be marked as
accounting categories.
These product categories can have accounting properties such as
`Taxes <account:model-account.tax>`, and revenue and expense
`Accounts <account:model-account.account>` associated with them.

When placing categories into a structure all the categories in the structure
must be either standard categories or accounting categories.
This means an accounting category cannot have a standard category as its
parent or as any of its subcategories.

.. seealso::

   The `Product Category <product:model-product.category>` concept is
   introduced by the :doc:`Product Module <product:index>`.

.. _model-analytic_account.rule:

Analytic Account Rule
=====================

The *Account Product Module* extends the *Analytic Account Rules* allowing
`Products <concept-product>` and `Categories <model-product.category>` to be
used as criteria by the analytic rule engine.

.. note::

   This feature is only available when the *Analytic Account Module* is
   activated.

.. seealso::

   The *Analytic Account Rule* concept is introduced by the :doc:`Analytic
   Account Module <analytic_account:index>`.
