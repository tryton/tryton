Purchase Requisition Module
###########################

The Purchase Requisition module allows users to create their purchase
requisitions.
Those requisitions will be approved or rejected by the Approval group.
On approval, purchase requests will be created.

Requisition
***********

- Employee: The requester.
- Description: The description of the purchase requisition.
- Supply Date: The expected date to supply.
- Currency: define the currency to use for this requisition. All product prices
  will be computed accordingly.
- Warehouse: Define the warehouse where the shipment will be made.
- Purchase Requisition Lines:

  - Supplier: The supplier.
  - Product: An optional reference to the product to request.
  - Description: The description of the product to request.
  - Quantity: The quantity to request.
  - Unit: The unit of measure in which is expressed the quantity.
  - Unit Price: The unit price of the product expressed in the currency of the
    purchase requisition.
  - Amount: The amount of the current line (Unit Price multiplied by Quantity).

- Total: The total amount.
- State: The state of the purchase requisition. May take one of the following
  values: Draft, Waiting, Rejected, Processing, Done, Cancelled.
- Company: The company which issue the purchase requisition.
