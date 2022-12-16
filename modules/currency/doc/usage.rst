*****
Usage
*****

In order to perform conversions between currencies exchange rates must be
defined.

.. _Setting currency exchange rates:

Setting currency exchange rates
===============================

All the `Currency <model-currency.currency>` values are relative.
Best practice is to define which currency you want to use as the base currency
by setting its exchange `Rate <model-currency.currency.rate>` to 1 for the
date when it is first used.
Then the rates of all other currencies are set as a multiplier of the base
currency.

In order to set an exchange rate of ``1.0 EUR = 1.1222 USD`` for the 1st of
January the following records should be created:

* A rate of ``1.0`` for the :abbr:`EUR (Euro)` currency with the 1st of
  January as the date.
* A rate of ``1.1222`` for the :abbr:`USD (US Dollar)` currency with the 1st
  of January as the date.

If you then wanted to update the exchange rate to ``1.0 EUR = 1.1034 USD`` for
the 15th of January you just need to set the rate on the USD currency to
``1.1034`` for that date.

.. note::

   In this example, as there isn't any rate set for the dates between the 2nd
   and 14th of January the last available rate will be used.
   Here this rate would be ``1.1222`` as this was the rate set for the 1st of
   January.

.. _Scheduling rate updates:

Scheduling rate updates
=======================

You may want to define some `Scheduled Rate Updates <model-currency.cron>` to
keep the `Exchange Rates <model-currency.currency.rate>` up to date.
When doing this you have to pick a source, the base `currency
<model-currency.currency>` and a frequency.
Then for each required date since the last update, a rate of ``1.0`` will be
set for the base currency and the corresponding rate will be set for each of
the selected currencies.

.. warning::

   It is strongly advised to use the same base currency for all *Scheduled Rate
   Updates*.

.. note::

   The currency module only supports the rates provided by the `European
   Central Bank`_, but third party modules can add additional sources for
   exchange rates.

.. _European Central Bank: https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html
