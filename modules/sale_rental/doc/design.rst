******
Design
******

The *Sale Rental Module* introduces and extends the following concepts.

.. _concept-product:

Product
=======

The *Product* concept is extended to store properties when they can be rented
such as a rental `Unit <product:model-product.uom>` and prices.

The rental price is calculated using the first :guilabel:`Rental Prices` that
matches the criteria such as the duration.

.. seealso::

   The `Product <product:concept-product>` concept is introduced by the
   :doc:`Product Module <product:index>`.

.. _model-product.category:

Product Category
================

The *Sale Rental Module* adds some properties to accounting categories when the
`Product <concept-product>` is rent such as `Account
<account:model-account.account>` and `Taxes <account:model-account.tax>`.

.. seealso::

   The accounting `Product Category <account_product:model-product.category>`
   concept is introduced by the :doc:`Account Product Module
   <account_product:index>`.

.. _model-sale.rental:

Rental
======

The *Rental* concept is used to manage the renting process of assets or
services.
Each rental, at any time, can be in one of several different states.
A rental progresses through these states until it is either done or gets
cancelled.
When some of these state changes happen the `Employee
<company:model-company.employee>` that triggered the state change is also
recorded.

Each rental contains details about the `Party <party:model-party.party>`
renting, included details such as the party's preferred `Contact Method
<party:model-party.contact_mechanism>`, and what `Address
<party:model-party.address>` the invoices must be sent to.

A rental is identified by a unique number that is generated automatically from
the `configured sequence <model-sale.configuration>`.
It also has other general information like the rental dates, description, and
reference used by the customer.

The rental is made up from one, or more, rental lines.
These lines can be arranged into a particularorder, if required.
The lines provide information about which quantity of `Products
<product:concept-product>` is rented.

The total, untaxed and tax amounts for a rental are derived from the duration,
quantity, prices and `Taxes <account:model-account.tax>` of the rental's lines.

Once confirmed, the rental lines must be picked up to register the start date,
and then returned to register the end date.
If the rented product is an asset, `Stock Moves <stock:model-stock.move>` are
created to record the outgoing and incoming transaction in the `Warehouse
<stock:concept-stock.location.warehouse>`.

`Invoices <account_invoice:model-account.invoice>` can be generated for the
returned products.
A final invoice is generated when the last product is returned.

.. seealso::

   Rentals are found by opening the main menu item:

      |Sales --> Rentals|__

      .. |Sales --> Rentals| replace:: :menuselection:`Sales --> Rentals`
      __ https://demo.tryton.org/model/sale.rental

Wizards
-------

.. _wizard-sale.rental.pickup:

Pickup
^^^^^^

The *Pickup* wizard is used to register product pickups on a specified date.

.. _wizard-sale.rental.return:

Return
^^^^^^

The *Return* wizard is used to register the return of products on a specified
date.

.. _model-sale.configuration:

Configuration
=============

The *Sale Configuration* concept is extended to store the `Sequence
<trytond:model-ir.sequence>` used to number the `Rental <model-sale.rental>`.

.. seealso::

   The `Sale Configuration <sale:model-sale.configuration>` concept is
   introduced by the :doc:`Sale Module <sale:index>`.

.. _model-stock.location:

Location
========

.. _concept-stock.location.warehouse:

Warehouse
---------

When the *Sale Rental Module* is activated, the warehouses gain some extra
properties to store rental locations such as the rental , picking and return
locations.

.. seealso::

   The `Warehouse <stock:concept-stock.location.warehouse>` concept is
   introduced by the :doc:`Stock Module <stock:index>`.
