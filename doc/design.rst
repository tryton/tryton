******
Design
******

The *Sale Module* introduces the concepts that are required to manage sales.
It also extends existing concepts so sales become an fully integrated part of
the system.

.. _model-sale.sale:

Sale
====

The *Sale* concept is used to manage the selling process.
Each sale, at any time, can be in one of several different states.
A sale progress though these states until it is either done or gets cancelled.
When some of these state changes happen the
`Employee <company:model-company.employee>` that triggered the state change
is also recorded.

Each sale contains details of the `Party <party:model-party.party>` that the
sale is made to, including details such as the party's preferred
`Contact Method <party:model-party.contact_mechanism>`, and what
`Addresses <party:model-party.address>` the shipments and invoices must be
sent to.

A sale is identified by a unique number that is generated automatically from
the configured *Sequence*.
It also has other general information like a sale date, description, and
reference used by the customer.

The sale is made up from one, or more, sales lines.
These lines can be arranged into a particular order, if required.
Normally most sales lines provide information about which
`Products <product:concept-product>` or items are included in the sale.
Extra lines can be added for things like titles, comments or subtotals.

The total, untaxed, and tax amounts for a sale are derived from the amounts,
prices and `Taxes <account:model-account.tax>` of the sale's lines.

For sales of physical items, such as goods or assets, the
`Warehouse <stock:concept-stock.location.warehouse>` the items are dispatched
from is required.
The sale's shipment method determines whether
`Customer Shipments <stock:model-stock.shipment.out>` are automatically created
for the sale, and when during the process this happens.
If customer shipments do get created then the
`Stock Moves <stock:model-stock.move>` on these shipments are linked to the
sale lines and must be recreated or ignored if they get cancelled.

`Invoices <account_invoice:model-account.invoice>` can be generated
automatically at the correct time based on the invoice method.
These invoices are created from data taken from the sale, and when invoicing
based on shipment they also use the quantities from the shipments.
The invoices are tracked by the sale, and if they are cancelled they must
either be recreated or ignored.

.. seealso::

   Sales are found by opening the main menu item:

      |Sales --> Sales|__

      .. |Sales --> Sales| replace:: :menuselection:`Sales --> Sales`
      __ https://demo.tryton.org/model/sale.sale

Reports
-------

.. _report-sale.sale:

Sale Report
^^^^^^^^^^^

The *Sale Report* is a document that can be printed out that contains all the
relevant information about each sale, including the lines which have been
sold.

Wizards
-------

.. _wizard-sale.handle.shipment.exception:

Handle Shipment Exception
^^^^^^^^^^^^^^^^^^^^^^^^^

The *Handle Shipment Exception* wizard helps the user ensure each sale
has the correct `Stock Moves <stock:model-stock.move>` associated with it.
For stock moves that have been cancelled, it lets the user decide which
should be re-created, and which should be ignored.

.. _wizard-sale.handle.invoice.exception:

Handle Invoice Exception
^^^^^^^^^^^^^^^^^^^^^^^^^

The *Handle Invoice Exception* wizard helps the user make sure each sale
only has the appropriate `Invoices <account_invoice:model-account.invoice>`
associated with it.
If any of the sale's invoices get cancelled this wizard provides the user
with the option to re-create or ignore the cancelled invoice.

.. _wizard-sale.modify_header:

Modify Header
^^^^^^^^^^^^^

Some fields on a draft sale become read-only when lines are added to it.
The *Modify Header* wizard allows the values in these fields to be safely
updated.

.. _wizard-sale.return_sale:

Return Sale
^^^^^^^^^^^

The *Return Sale* wizard is used when a customer returns all or part of a sale.
It creates new draft sales that match any selected sales, but with all the
quantities negated.

.. _model-product.sale.context:

Sale Context
============

The *Sale Context* allows the user to set a context in which a
`Product's <product:concept-product>` properties are then calculated.

This is used when showing a list of salable products.
It allows the user to select a customer and some other properties,
and then get a list of products that are available along with their prices
in the selected `Currency <currency:model-currency.currency>`.

.. seealso::

   The Sale Context is used to provide context in the main menu item:

      |Sales --> Salable Products|__

      .. |Sales --> Salable Products| replace:: :menuselection:`Sales --> Salable Products`
      __ https://demo.tryton.org/model/product.product;context_model=product.sale.context

.. _concept-sale.reporting:

Sale Reporting
==============

Each of the different *Sale Reporting* concepts are based on either an
``Abstract`` sales report, or an ``AbstractTimeseries``.
There is also a base ``Context`` that is inherited and used to specify things
such as the date range that is used by the report.

The ``Abstract`` provides the basic properties that makes up a sales report
including the number of sales and revenue.
The ``AbstractTimeseries`` is used to extend this with a date.
This is used in sales reports that cover multiple periods of time.
These are combined together with additional specific properties to create the
different sales reports.

.. seealso::

   Sales reports can be accessed from the main menu item:

      :menuselection:`Sales --> Reporting --> Sales`

.. _model-sale.reporting.customer:
.. _model-sale.reporting.customer.time_series:

By Customer
-----------

The sales reporting that is done *By Customer* splits the sales up based on
what each `Customer <party:model-party.party>` bought.
This is done in two separate parts.
One that shows the sales, in total, for the selected period from the
``Context``.
Another that breaks them down by date into smaller chunks.

.. _model-sale.reporting.product:
.. _model-sale.reporting.product.time_series:

By Product
----------

Sales reporting that is done *By Product* splits up the sales based on the
`Product <product:concept-product>` that was sold.
This is structured as two parts.
One that shows the total sales for the selected period of time, and another
that shows how the sales were distributed over time.

.. _model-sale.reporting.category.tree:
.. _model-sale.reporting.category:
.. _model-sale.reporting.category.time_series:

By Category
-----------

The *By Category* sales reporting shows the sales based on the
`Category <product:model-product.category>` that a product is in.
This works in the same way as the `By Product <model-sale.reporting.product>`
sales reporting, but there is also an additional report that shows the
categories in their natural tree structure.

.. _model-sale.reporting.region:

By Region
---------

The sales reporting that is done *By Region* shows sales based on where the
customer is located.
This is done by combining together in a tree structure the sales
`By Country <model-sale.reporting.country>` below which are the sales
`By Subdivision <model-sale.reporting.country.subdivision>`.

.. _model-sale.reporting.country:
.. _model-sale.reporting.country.time_series:

By Country
^^^^^^^^^^

The *By Country* concept groups sales based on the
`Country <country:model-country.country>` in which the customer is located.
This is done in two parts, one for total sales and one showing how the sales
were distributed over time.

.. _model-sale.reporting.country.subdivision:
.. _model-sale.reporting.country.subdivision.time_series:

By Subdivision
^^^^^^^^^^^^^^

The *By Subdivision* concept groups sales based on which
`Subdivision <country:model-country.subdivision>` of a country a customer is
located.
This is done in two parts, one for total sales and one showing how the sales
were distributed over time.

Wizards
^^^^^^^

.. _wizard-sale.reporting.region.open:

Open Region
"""""""""""

The *Open Region* wizard ensures that the correct type of time series gets
opened.
This may be a time series for either a country, or subdivision, depending on
what line from the `By Region <model-sale.reporting.region>` was opened.

.. _model-sale.configuration:

Configuration
=============

The *Sale Configuration* concept is used for the settings that affect the
general behaviour and default values for sales related activities.

.. note::

   Some of the sales configuration options have no effect unless the
   :doc:`Task Queue<trytond:topics/task_queue>` has been setup and some
   workers are running.

.. seealso::

   Sales configuration settings are found by opening the main menu item:

      |Sales --> Configuration --> Sales Configuration|__

      .. |Sales --> Configuration --> Sales Configuration| replace:: :menuselection:`Sales --> Configuration --> Sales Configuration`
      __ https://demo.tryton.org/model/sale.configuration/1
