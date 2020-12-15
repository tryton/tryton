******
Design
******

The *Currency Module* introduces the following concepts:

.. _model-currency.currency:

Currency
========

Each currency of interest is represented in Tryton by a currency record.
These currencies are used together with a numeric value to represent an amount
of money.
Tryton can convert monetary amounts from one currency to another using the
exchange `Rate <model-currency.currency.rate>` for a given date.
This is important for multi-currency transactions, and if you want to manage
money in a range of different currencies.

.. seealso::

   Currencies can be found by opening the main menu item:

      |Currency --> Currencies|__

      .. |Currency --> Currencies| replace:: :menuselection:`Currency --> Currencies`
      __ https://demo.tryton.org/model/currency.currency

.. _model-currency.currency.rate:

Rate
====

The exchange rates that are used when converting money between
`Currencies <model-currency.currency>` are saved next to their associated
currencies.
As exchange rates vary over time they are stored along with the date from
when they apply.
All exchange rates are relative with respect to each other.
