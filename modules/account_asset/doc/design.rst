******
Design
******

The *Account Asset Module* introduces the following concepts:

.. _model-account.asset:

Asset
=====

The main concept introduced by the *Account Asset Module* is the *Asset*.
It contains details of how to calculate the depreciation of a purchased
quantity of fixed assets.

Each asset has a product of type :guilabel:`Assets`, a number and the values to
be depreciated.

.. note::

   Most of the properties are filled in automatically when a supplier invoice
   line is set.

When the asset is run, lines are calculated for each date based on the frequency
and the method for the period defined by the start and end dates.
Each line stores the actual value and the depreciation of the asset for that
date.

.. note::

   The asset lines can be tested before the asset is run using the
   :guilabel:`Create Lines` and :guilabel:`Clear Lines` buttons.


.. seealso::

   The Assets can be found by opening the main menu item:

      |Financial --> Assets --> Assets|__

      .. |Financial --> Assets --> Assets| replace:: :menuselection:`Financial --> Assets --> Assets`
      __ https://demo.tryton.org/model/account.asset

Wizards
-------

.. _wizard-account.asset.create_moves:

Create Assets Moves
^^^^^^^^^^^^^^^^^^^

The *Create Assets Moves* wizard creates and posts the `Account Moves
<account:model-account.move>` for each line of running *assets* up to the date
entered.

.. seealso::

   The Create Assets Moves can be launched from the main menu item:

      |Financial --> Assets --> Create Assets Moves|__

      .. |Financial --> Assets --> Create Assets Moves| replace:: :menuselection:`Financial --> Assets --> Create Assets Moves`
      __ https://demo.tryton.org/wizard/account.asset.create_moves

.. _wizard-account.asset.update:

Update Asset
^^^^^^^^^^^^

The *Update Asset* wizard allows the modification of the values or the end date
of a running *asset*.
A revision is created and an `Account Move <account:model-account.move>` is
posted to record the change in value, and the remaining lines are recalculated
based on the new values and date.

Reports
-------

.. _report-account.asset.depreciation_table:

Depreciation Table
^^^^^^^^^^^^^^^^^^

The *Depreciation Table* report prints an amortization table of all the running
assets for a given period.

.. _model-account.configuration:

Account Configuration
=====================

The *Account Configuration* is extended to store the settings for the *assets*
such as the numbering sequence or the rules for calculating the date for
posting the depreciation `moves <account:model-account.move>`.

.. seealso::

   The `Account Configuration <account:model-account.configuration>` concept is
   introduced by the :doc:`Account Module <account:index>`.

.. _model-account.account.type:

Account Type
============

The *Account Type* is extended to define which `Accounts
<account:model-account.account>` can be used to post the depreciation of fixed
assets.

.. seealso::

   The `Account Type <account:model-account.account.type>` concept is
   introduced by the :doc:`Account Module <account:index>`.


.. _model-account.journal:

Account Journal
===============

When the *Account Asset Module* is activated, the *Account Journal* gets a new
type :guilabel:`Asset`, which is used to post the depreciation of the *assets*.

.. seealso::

   The `Account Journal <account:model-account.journal>` concept is introduced
   by the :doc:`Account Module <account:index>`.

.. _concept-product:

Product
=======

The *Product* concept is extended to specify whether an asset is depreciable
and over what duration.

.. seealso::

   The `Product <product:concept-product>` concept is introduced by the
   :doc:`Product Module <product:index>`.

.. _model-product.category:

Product Category
================

When the *Account Asset Module* is activated, the accounting *Product Category*
acquires some additional accounting properties such as the depreciation
`account <account:model-account.account>` and asset account used for posting.

.. seealso::

   The accounting `Product Category <account_product:model-product.category>`
   concept is introduced by the :doc:`Account Product Module
   <account_product:index>`.
