Purchase Request For Quotation Module
#####################################

The Purchase Request for Quotation module allows users to ask quotations
from selected purchase requests to different suppliers.
Each request will collect quotation information from the supplier.
The selection of the quotation is done by taking either the
preferred_quotation field if not empty otherwise the first one ordered
from the received quotations.

Quotation
*********

- Supplier: The supplier.
- Company: The company which issue the request quotation.
- Supplier Address: The address of the supplier.
- Lines:

  - Product: An optional reference to the product to quote.
  - Description: The description of the product to quote.
  - Supply Date: The expected date to supply.
  - Quantity: The quantity to quote.
  - Unit: The unit of measure in which is expressed the quantity.
  - Unit Price: The unit price of the product expressed in the currency.
  - Currency: define the currency to use for this quotation. All product prices
    will be computed accordingly.

- State: The state of the quotation. May take one of the following
  values: *Draft*, *Sent*, *Received*, *Rejected*, *Cancelled*.
