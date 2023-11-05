******
Design
******

The *Sale Opportunity Module* introduces concepts to manage leads and
opportunities.

.. _model-sale.opportunity:

Sale Opportunity
================

The *Sale Opportunity* concept is used to manage pre-sale processes such as
leads and opportunities.
Each sales opportunity can, at any time, be in one of several different states
reflecting its progress.
A sales opportunity progresses through these states until it is either won or
lost.
When some of these state changes happen the `Employee
<company:model-company.employee>` that triggered the state change is also
recorded.

Each sales opportunity may contain details about the possible future sale, such
as the `Party <party:model-party.party>` the sale would be to, and what
`Addresses <party:model-party.address>` may be involved.

A sale opportunity is identified by a unique number that is generated
automatically from the `configured <sale:model-sale.configuration>` *Sequence*.
It also has other general information like a description, start and end date,
conversion probability and reference used by the customer.

The sales opportunity may be made up from one or more, opportunity lines.
These lines can be arranged into a particular order, if required.
The lines provide information about which `Products <product:concept-product>`
may be sold.

A `Sale <sale:model-sale.sale>` is generated automatically when the sale
opportunity is converted.
The sales opportunity is then considered to be won when any of the related sales
are confirmed.
If, however, all of the sales related to the sales opportunity are cancelled
then the sales opportunity is considered to be lost.

.. seealso::

   Leads and Opportunities are found by opening the main menu item:

      |Sales -> Leads and Opportunities|__

      .. |Sales -> Leads and Opportunities| replace:: :menuselection:`Sales -> Leads and Opportunities`
      __ https://demo.tryton.org/model/sale.opportunity

.. _concept-sale.opportunity.reporting:

Sale Opportunity Reporting
==========================

Each of the different *Sale Opportunity Reporting* concepts are based on either
an ``Abstract``, an ``AbstractTimeseries``, an ``AbstractConversion`` or
an ``AbstractConversionTimeseries`` sales opportunities report.
There is also a base ``Context`` that is inherited and used to specify things
such as the date range that is used by the report.

The ``Abstract`` report base provides the basic properties that make up the
report including the number, rates and amount of sale opportunities converted.
The ``AbstractTimeseries`` extends this with a date.
This is used in sale opportunities reports that cover multiple periods of time.
The ``AbstractConversion`` and ``AbstractConversionTimeseries`` extend the
corresponding report bases to include properties about wins and losses.
These are combined together with additional specific properties to create the
different sales opportunities reports.

.. seealso::

   The Sales Opportunity Reports can be accessed from the main menu item:

      :menuselection:`Sales --> Reporting --> Opportunities`

.. _model-sale.opportunity.reporting.conversion.employee:
.. _model-sale.opportunity.reporting.conversion.employee.time_series:

Per Employee
------------

The reporting for sale opportunities conversions *Per Employee* splits the sales
opportunities up based on what each `Employee <company:model-company.employee>`
converted.
This is done in two separate parts.
One that shows the sale opportunities, in total, for the selected period from
the ``Context``.
Another that breaks them down by date into smaller chunks.
