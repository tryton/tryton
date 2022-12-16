******
Design
******

The *Sale Point Module* introduces the concepts that are required to manage
retail sales.

.. _model-sale.point:

Point of Sale
=============

The *Point of Sale* concept is used to configure the point where sales happen.

.. seealso::

   The Point of Sale configuration is found by opening the main menu item:

      |Sales --> Configuration --> Points of Sale|__

      .. |Sales --> Configuration --> Points of Sale| replace:: :menuselection:`Sales --> Configuration --> Points of Sale`
      __ https://demo.tryton.org/model/sale.point

.. _model-sale.point.sale:

Sale
====

The *Sale* concept registers what quantity of products are sold or returned and
how the customer paid for them.
Each sale, at any time, can be in one of several different states.
A sale progress though these states until it is posted.

Each sale is linked to a `Point <model-sale.point>` where it takes place.

A sale is identified by a unique number that is generated automatically from
the configured *Sequence* for the sale Point.
It also has other general information like the date and the `Employee
<company:model-company.employee>` who creates the order.

The sale is made up from one, or more, sales lines.
These lines provide information about which `Products
<product:concept-product>` and what quantities are included in the sale.

The total and tax amounts for a sale are derived from the prices and `Taxes
<account:model-account.tax>` of the line's Products.

The amount paid or reimbursed is registered using the `Payment Method
<model-sale.point.payment.method>`.
Once the amount to paid reaches zero, the sale is done.

On posting the sale it generates the corresponding `Stock Moves
<stock:model-stock.move>` for the goods and posts the corresponding `Account
Move <account:model-account.move>`.

.. seealso::

   Sales are found by opening the main menu item:

      |Sales --> POS Sales|__

      .. |Sales --> POS Sales| replace:: :menuselection:`Sales --> POS Sales`
      __ https://demo.tryton.org/model/sale.point.sale

Wizards
-------

.. _wizard-sale.point.sale.pay:

Pay Sale
^^^^^^^^

The *Pay Sale* wizard allows payments to be registered against the sale.
If the sale is overpaid the wizard calculates the amount to return.
Once the sale is fully paid the sale state is automatically set to done.

.. _model-sale.point.cash.session:

Cash Session
============

The *Cash Session* groups the cash payments and the transfers of a `Point of
Sale <model-sale.point>` over a period.
The sessions of a point of sale are a chained list that tracks the cash amount
between each closure.

.. seealso::

   The Cash Sessions are found by opening the main menu item:

      |Sales --> POS Cash Sessions|__

      .. |Sales --> POS Cash Sessions| replace:: :menuselection:`Sales --> POS Cash Sessions`
      __ https://demo.tryton.org/model/sale.point.cash.session
.. _model-sale.point.payment.method:

Payment Method
==============

The *Payment Method* defines the available options for paying a `Sale
<model-sale.point.sale>`.

A method can be set to *cash* so it will be used to return change.
Only one method per company can be set to cash.

.. seealso::

   Payment Methods are found by opening the main menu item:

      |Sales --> Configuration --> POS Payment Methods|__

      .. |Sales --> Configuration --> POS Payment Methods| replace:: :menuselection:`Sales --> Configuration --> POS Payment Methods`
      __ https://demo.tryton.org/model/sale.point.payment.method

.. _model-sale.point.cash.transfer.type:

Cash Transfer Type
==================

The *Transfer Type* defines the available options for transferring cash of a
`Point of Sale <model-sale.point>`.

.. seealso::

   Cash Transfer Types are found by opening the main menu item:

      |Sales --> Configuration --> POS Cash Transfer Types|__

      .. |Sales --> Configuration --> POS Cash Transfer Types| replace:: :menuselection:`Sales --> Configuration --> POS Cash Transfer Types`
      __ https://demo.tryton.org/model/sale.point.cash.transfer.type
