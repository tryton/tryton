Stock Forecast Module
*********************

The *Stock Forecast Module* introduces this concepts:

.. _model-stock.forecast:

Forecast
========

A *Forecast* represents the expected demand for some `Products
<concept-product>` over a set period of time.
Each *Forecast* has properties that holds information about the `Warehouse
<stock:concept-stock.location.warehouse>`, period and destination `Location
<stock:model-stock.location>` that is expected to require the stock.
It also has a set of lines which list how much of each product will be shipped
or received.

The forecasts are automatically deactivated after their period has passed.

.. seealso::

   Forecasts are found by opening the main menu item:

      |Inventory & Stock --> Forecasts|__

      .. |Inventory & Stock --> Forecasts| replace:: :menuselection:`Inventory & Stock --> Forecasts`
      __ https://demo.tryton.org/model/stock.forecast


Wizards
-------

.. _wizard-stock.forecast.complete:

Complete Forecast
^^^^^^^^^^^^^^^^^

The *Complete Forecast* calculates forecast lines based on `Stock Moves
<stock:model-stock.move>` that have happened in the past.
