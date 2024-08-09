******
Design
******

The *European Account Module* introduces and extends the following concepts:

.. _model-account.ec_sales_list:

EC Sales List
=============

The *EC Sales List* provides the details of sales to other :abbr:`VAT (Value
Added Tax)` registered companies in other :abbr:`EU (European Union)`
countries.

.. seealso::

   The EC Sales List is found by opening the main menu item:

      |Financial --> Reporting --> EC Sales List|__

      .. |Financial --> Reporting --> EC Sales List| replace:: :menuselection:`Financial --> Reporting --> EC Sales List`
      __ https://demo.tryton.org/model/account.ec_sales_list;context_model=account.ec_sales_list.context

.. _model-account.tax:

Tax
===

When the *European Account Module* is activated, the *Tax* gets a new property
to store the tax's :guilabel:`EC Sales List Code`.
This is then used to select which taxes to include on the `EC Sales List
<model-account.ec_sales_list>`.

.. seealso::

   The `Tax <account:model-account.tax>` concept is introduced by the
   :doc:`Account Module <account:index>`.
