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

  The moves between the storage location and the production location (as
  defined on the warehouse) for products used for production.

* Outputs

  The moves between the production location and the storage location for
  products produced.

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

* Cancel

  All moves are cancelled.

The cost of the production is computed with the sum of the cost price of all
incoming products. If a product is selected, it will have the cost as unit
price. The production verify that all the cost is spread on the unit price of
output moves.
