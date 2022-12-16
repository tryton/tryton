Sale Supply Drop Shipment Model
###############################

The Sale Supply Drop Shipment module adds a drop shipment option on product
supplier if "supply on request" is checked. When checked, the purchase request
and the linked purchase have the address of customer as Delivery Address;
at the confirmation of the purchase a drop shipment is created and linked to
both the purchase and the sale.

Drop Shipment
*************

A drop shipment is used when products are sent directly from the supplier to
the customer without going through the warehouse.
It is mainly composed of a supplier, a customer and a list of moves.

The drop shipment can be in one of this states:

* Draft

  All moves are in draft.

* Waiting

  All moves are in draft, the synchronization between the moves of the supplier
  and the moves to the customer has occurred.

* Shipped

  All moves from the supplier are done.

* Done

  All moves are in state Done.

* Cancelled

  All moves are cancelled.
