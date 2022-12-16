.. _model-stock.period:

Period
======

In Tryton a stock *Period* is used to group together the all stock moves that
happened up to a specific date and that were also done after the date of any
previous stock *Period*.

This allows the stock levels for the `Products <concept-product>` in all stock
`Locations <model-stock.location>` to be calculated for the date of the period,
and stored in the `Stock Period Cache <model-stock.period.cache>`.

These cached values can then be used, where applicable, instead of having to
recalculate them each time they are needed.

.. seealso::

   The periods can be viewed and managed from the main menu item:

      |Inventory & Stock --> Configuration --> Periods|__

      .. |Inventory & Stock --> Configuration --> Periods| replace:: :menuselection:`Inventory & Stock --> Configuration --> Periods`
      __ https://demo.tryton.org/model/stock.period

.. _model-stock.period.cache:

Period Cache
============

The *Period Cache* is used to store the quantities of a product in a
particular location on the date defined by its `Period <model-stock.period>`.
