Stock Supply Module
###################

The Stock Supply module add automatic supply mechanisms and introduce
the concepts of order point and purchase request.


Purchase Request
****************

A purchase request define the need for the purchase of a product. It
is linked to a warehouse and eventually a supplier, it contains a
ideal purchase date and an expected supply date. A purchase request
can be in one of these states:

* Draft

  A draft purchase request is a request that is not linked to a
  purchase.

* Purchased

  A Purchased request is a request that is linked to a purchase which
  is not in state Done or Cancel.

* Done

  A purchase request is in state Done if it is linked to a Purchase
  which is in state Done.

* Cancel

  A purchase request is in state Cancel if it is linked to a Purchase
  which is cancelled.

A wizard allow to create purchases based on a selection of Draft
purchase requests. The new purchases contains one purchase line by
purchase request and group them by warehouse and by supplier. Once the
purchases are created, the corresponding purchase requests are set to
the state Purchased.


Order Point
***********

An order point define minimum and maximum quantities for a product on
a location. The minimum quantity is the quantity that should be always
(if possible) available. The maximum is a target quantity that should
be reached when re-ordering. An order point also define a type which
can be:

* Internal

  An Internal order point is defined on a Storage location, it also
  define a provisioning location. If the minimum quantity is reached
  it will result in the creation of an internal shipment between the
  provisioning location and the Storage location.

* Purchase

  A Purchase order point is defined on a warehouse location. If the
  minimal quantity is reached on the warehouse it will result in a
  purchase request.

The internal shipments and purchase requests are created by schedulers
with respect to stock levels and existing shipments and requests. The
stock levels are computed between the next two supply dates. If the
stock level of a product without order point on the given warehouse is
below zero, a purchase request is also created.
