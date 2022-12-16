******
Design
******

The *Purchase Module* introduces some new concepts and updates existing
concepts to make them work seamlessly with purchases.

.. _model-purchase.purchase:

Purchase
========

The *Purchase* is used to manage the purchasing process.
Each purchase, at any time, can be in one of several different states.
A purchase progresses through these states until eventually it is either done
or gets cancelled.
When some of these state changes happen the
`Employee <company:model-company.employee>` that triggered the state change is
also recorded.

Details are stored about the `Company <company:model-company.company>` making
the purchase and any other `Parties <party:model-party.party>`,
`Contact Mechanisms <party:model-party.contact_mechanism>` and
`Addresses <party:model-party.address>` that relate to it, such as the
supplier, the contact at the supplier or the party that is sending the
`Invoice <account_invoice:model-account.invoice>`.

A purchase is identified by a unique number that is generated automatically
from the configured *Sequence* and may also have other general information such
as the purchase date, a description, or a reference provided by the supplier.

Each purchase is made up from one or more lines.
These lines can be put into a particular order if desired.
Normally most lines on a purchase provide information about which
`Products <product:concept-product>` or items are required.
Informational lines can also be added for things like titles, comments or
subtotals.

The total, untaxed, and tax amounts for a purchase are derived from the
amounts, prices and `Taxes <account:model-account.tax>` of the purchase's
lines.

A destination `Warehouse <stock:concept-stock.location.warehouse>` is required
for purchases of physical items such as goods or assets.
The purchase will automatically create `Stock Moves <stock:model-stock.move>`
for these products.
These stock moves are linked to the purchase's lines and must be
recreated or ignored if they get cancelled.

`Invoices <account_invoice:model-account.invoice>` relating to the purchase
may be created, depending on which invoice method is selected.
These invoices are based on the details from the purchase, and must be
recreated or ignored if they get cancelled.

.. seealso::

   Purchases can be found by opening the main menu item:

      |Purchase --> Purchases|__ menu item.

      .. |Purchase --> Purchases| replace:: :menuselection:`Purchase --> Purchases`
      __ https://demo.tryton.org/model/purchase.purchase

Reports
-------

.. _report-purchase.purchase:

Purchase Report
^^^^^^^^^^^^^^^

The *Purchase Report* provides a purchase order that can be sent to the
supplier when making a purchase.
It includes all the relevant information from the selected purchases.

Wizards
-------

.. _wizard-purchase.handle.shipment.exception:

Handle Shipment Exception
^^^^^^^^^^^^^^^^^^^^^^^^^

The *Handle Shipment Exception* wizard helps the user ensure the purchase
has the correct `Stock Moves <stock:model-stock.move>` associated with it.
For stock moves that have been cancelled, it lets the user decide which
should be re-created, and which should be ignored.

.. _wizard-purchase.handle.invoice.exception:

Handle Invoice Exception
^^^^^^^^^^^^^^^^^^^^^^^^

The *Handle Invoice Exception* wizard helps the user make sure the purchase
only has the appropriate `Invoices <account_invoice:model-account.invoice>`
associated with it.
If any of the purchase's invoices get cancelled this wizard provides the user
with the option to re-create or ignore the cancelled invoice.

.. _wizard-purchase.modify_header:

Modify Header
^^^^^^^^^^^^^

Some fields on a draft purchase become read-only when lines are added to it.
The *Modify Header* wizard allows the values in these fields to be safely
updated.

.. _wizard-purchase.return_purchase:

Return Purchase
^^^^^^^^^^^^^^^

The *Return Purchase* wizard is used when a purchase needs to be sent back.
It creates new draft purchases that match any selected purchases, but with
all the quantities negated.

.. _model-purchase.product_supplier:

Product Supplier
================

The *Product Supplier* concept links together a
`Product <product:concept-product>` with a `Party <party:model-party.party>`
that acts as a supplier.
The product can be either a `Product Template <product:model-product.template>`
or one of its `Variants <product:model-product.product>`.
Each `Company <company:model-company.company>` has their own list of product
suppliers.

A supplier's product name and code, and a lead time can be defined for each
combination of products and suppliers.
Also different purchase prices can be set for different minimum order
quantities.

.. seealso::

   A list of products and their suppliers can be found by opening the main
   menu item:

      |Products --> Products --> Suppliers|__

      .. |Products --> Products --> Suppliers| replace:: :menuselection:`Products --> Products --> Suppliers`
      __ https://demo.tryton.org/model/purchase.product_supplier

.. _concept-purchase.reporting:

Purchase Reporting
==================

Each of the different *Purchase Reporting* concepts are based on either an
``Abstract`` purchases report, or an ``AbstractTimeseries``.
There is also a base ``Context`` that is inherited and used to specify things
such as the date range that is used by the report.

The ``Abstract`` provides the basic properties that makes up a purchases report
including the number of purchases and expense.
The ``AbstractTimeseries`` is used to extend this with a date.
This is used in purchases reports that cover multiple periods of time.
These are combined together with additional specific properties to create the
different purchases reports.

.. seealso::

   Purchases reports can be accessed from the main menu item:

      :menuselection:`Purchases --> Reporting --> Purchases`

.. _model-purchase.reporting.supplier:
.. _model-purchase.reporting.supplier.time_series:

By Supplier
-----------

The purchases reporting that is done *By Supplier* splits the purchases up
based on what each `Supplier <party:model-party.party>` bought.
This is done in two separate parts.
One that shows the purchases, in total, for the selected period from the
``Context``.
Another that breaks them down by date into smaller chunks.

.. _model-purchase.reporting.product:
.. _model-purchase.reporting.product.time_series:

By Product
----------

Purchases reporting that is done *By Product* splits up the purchases based on
the `Product <product:concept-product>` that was purchased.
This is structured as two parts.
One that shows the total purchases for the selected period of time, and another
that shows how the purchases were distributed over time.

.. _model-purchase.configuration:

Configuration
=============

The *Purchase Configuration* concept is used to store the settings that affect
the general behaviour and default values for purchase related activities.

.. note::

   Some of the purchase configuration options have no effect unless the
   :doc:`Task Queue <trytond:topics/task_queue>` has been setup and some
   workers are running.

.. seealso::

   Purchase configuration settings are found by opening the main menu item:

      |Purchase --> Configuration --> Configuration|__

      .. |Purchase --> Configuration --> Configuration| replace:: :menuselection:`Purchase --> Configuration --> Configuration`
      __ https://demo.tryton.org/model/purchase.configuration/1
