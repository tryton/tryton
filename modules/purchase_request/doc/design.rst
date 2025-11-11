******
Design
******

The *Purchase Request Module* introduces some new concepts.

.. _model-purchase.request:

Purchase Request
================

The *Purchase Request* is used to manage the need to purchase `Products
<product:concept-product>`.
Each request stores several information such as the quantity to purchase, the
best purchase date and the expected supply date.
A purchase request progresses through several different states until it is
either done or gets cancelled.

.. note::
   The purchase requests are not meant to be created by the users.

.. seealso::

   Purchase Requests can be found by opening the main menu item:

      |Purchases --> Purchase Requests|__

      .. |Purchases --> Purchase Requests| replace:: :menuselection:`Purchases --> Purchase Requests`
      __ https://demo.tryton.org/model/purchase.request

Wizards
~~~~~~~

.. _wizard-purchase.request.create_purchase:

Create Purchase
^^^^^^^^^^^^^^^

The *Create Purchase* wizard creates `Purchases
<purchase:model-purchase.purchase>` for the selected draft purchase requests
grouped by `Warehouses <stock:concept-stock.location.warehouse>` and `Parties
<party:model-party.party>`.
Once purchased the request's state is updated following the state of the
purchase.

.. _wizard-purchase.request.handle.purchase.cancellation:

Handle Purchase Cancellation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The *Handle Purchase Cancellation* wizard helps the user to reset to draft or
cancel the requests for which the purchase has been cancelled.
