Production Module
#################

The production module defines basics for production management: Bill of
material and production order.


Bill of Material
****************

Bills of Material are list of products and quantities needed to produce a
product. It is often shorten with BOM.

Production
**********

A Production is mainly defined by a product, a BOM, a location, a quantity and
two lists of moves:

* Inputs

  The moves between the production picking location, or the storage location
  if product picking location is empty, and the production location
  (as defined on the warehouse) for products used for production.

* Outputs

  The moves between the production location and the production output
  location, or the storage location if production output is empty, for produced
  products.

The production can be in one of this states:

* Request

  The production is requested by the system.

* Draft

  Input and output moves are in draft.

* Waiting

  The production is waiting for action and all moves are still in draft.

* Assigned

  The input moves are assigned.

* Running

  The input moves are in state done.

* Done

  The output moves are in state done.

* Cancelled

  All moves are cancelled.

The cost of the production is computed with the sum of the cost price of all
incoming products. This cost is allocated to the output products based on the
list price of each (the product without a list price are considered as waste).

A cron task runs every day and updates the cost of productions if the cost
price of the incoming products has changed.


Rescheduling Production
-----------------------

It is possible to setup a cron task to reschedule the productions that are
planned to start in the past. By default they are rescheduled to today.
