Account Tax Rule Country
########################

The account_tax_rule module extends the tax rule to add origin and destination
countries as criteria.

Tax Rule Line
*************

Two criteria fields are added:

- From Country: The country of origin
- To Country: The country of destination

The countries are picked from the origin document:

- Sale:

  - The origin country comes from the address of the warehouse.
  - The destination country comes from the shipping address.

- Purchase:

  - The origin country comes from the invoice address.
  - The destination country comes from the address of the warehouse.
