Stock Supply Module
###################

The Stock Supply module add automatic supply mechanisms and introduce
the concepts of order point.

Order Point
***********

An order point define minimum, maximum and target quantities for a product on a
location.

* The minimum quantity is the threshold quantity below which the provisioning
  process will be triggered.

* The maximum quantity is the threshold quantity above which the overflowing
  process will be triggered. 

* The target quantity is the quantity that will be found in the location after
  the provisioning / overflowing process has been completed.

An order point also define a type which can be:

* Internal

  An Internal order point is defined on a Storage location, it also defines a
  provisioning and/or an overflowing location. If the minimum quantity is
  reached it will result in the creation of an internal shipment between the
  provisioning location and the Storage location. If the maximum quantity is
  reached it will result in the creation of an internal shipment between the
  storage location and the overflowing location.

* Purchase

  A Purchase order point is defined on a warehouse location. If the
  minimal quantity is reached on the warehouse it will result in a
  purchase request.

The internal shipments and purchase requests are created by the supply wizard
with respect to stock levels and existing shipments and requests. The
stock levels are computed between the next two supply dates computed over the
Supply Period from the configuration (default: 1 day). If the stock level of a
product without order point on the given warehouse is below zero, a purchase
request is also created.  The same happens if the stock level of a storage
location with a provisioning location is below zero. Likewise, if the stock
level of a storage is above zero and an overflow location is defined on the
location then an internal shipment will be created.
