******
Design
******

The *Purchase Request Quotation Module* introduces some new concepts.

.. _model-purchase.request.quotation:

Purchase Request For Quotation
==============================

The *Purchase Request for Quotation* model tracks quotes for `Purchase Requests
<purchase_request:model-purchase.request>` to multiple suppliers.
A request for quotation has a line consisting of a quantity, price and supply
date for each `Product <concept-product>` being quoted.

.. seealso::

   The Quotations can be found by opening the main menu item:

      |Purchases --> Purchase Requests --> Quotations|__

      .. |Purchases --> Purchase Requests --> Quotations| replace:: :menuselection:`Purchases --> Purchase Requests --> Quotations`
      __ https://demo.tryton.org/model/purchase.request.quotation

Reports
-------

.. _report-purchase.request.quotation:

Purchase Request Quotation
^^^^^^^^^^^^^^^^^^^^^^^^^^

The *Purchase Request Quotation* provides a request for quotation that can be
sent to the suppliers.
It includes the relevant information for the supplier to make the quotation.

Purchase Configuration
======================

When the *Purchase Request Quotation Module* is activated, the *Purchase
Configuration* receives a new property to store the `Sequence
<trytond:model-ir.sequence>` to number the `Purchase Request Quotation
<model-purchase.request.quotation>`.

.. seealso::

   The `Purchase Configuration <purchase:model-purchase.configuration>` concept
   is introduced by the :doc:`Purchase Module <purchase:index>`.

.. _model-purchase.request:

Purchase Request
================

When the *Purchase Request for Quotation Module* is activated, the purchase
request receives a list of `Quotation <model-purchase.request.quotation>` lines
from which it can select a preferred one to create a `Purchase
<purchase:model-purchase.purchase>`.

.. note::

   If the prefered quotation is empty, the received line with the lower price
   is used.

.. seealso::

   The `Purchase Request <purchase_request:model-purchase.request>` concept is
   introduced by the :doc:`Purchase Request Module <purchase_request:index>`.

Wizards
-------

.. _wizard-purchase.request.quotation.create:

Create Purchase Request Quotation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The *Create Purchase Request Quotation* wizard helps users to create quotations
for multiple suppliers and purchase requests.
