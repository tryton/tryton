Account Tax Rule Country
########################

The account_tax_rule module extends the tax rule to add origin and destination
countries and subdivisions as criteria.

Tax Rule Line
*************

Four criteria fields are added:

- From Country: The country of origin
- From Subdivision: The subdivision of origin
- To Country: The country of destination
- To Subdivision: The subdivision of destination

The countries are picked from the origin document:

- Sale:

  - The origin country and subdivision come from the address of the warehouse.
  - The destination country and subdivision come from the shipping address.

- Purchase:

  - The origin country and subdivision come from the invoice address.
  - The destination country and subdivision come from the address of the warehouse.

- Stock Consignment:

  - The origin country and subdivision come from the warehouse's address of the
    location or the delivery address for returned customer shipment.
  - The destination country and subdivision come from the warehouse's address
    of the location or the delivery address for customer shipment.
