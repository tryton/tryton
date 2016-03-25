Stock Supply Module
###################

The Stock Supply module add automatic supply mechanisms and introduce
the concepts of order point.

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
below zero, a purchase request is also created. The same happens if
the stock level of a storage location with a provisioning location is
below zero.
