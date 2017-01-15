Stock Supply Production Module
##############################

The Stock Supply Production module adds automatic supply mechanisms via
production request.

Production Request
******************

A production request is a production in the state request. It defines the need
to produce a product.


Order Point
***********

It adds a new type of Order Point:

* Production

  A Production order point is defined on a warehouse location. If the minimal
  quantity is reached at any time on the warehouse it will result in a
  production request.

The production requests are created by the supply wizard with respect to stock
levels and existing requests. The stock levels are computed on the supply
period define in the production configuration.
