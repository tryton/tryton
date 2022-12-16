Carrier Module
##############

The carrier module defines the concept of carrier.

Carrier
*******

A carrier links a party with a product and cost method.

- The *Product* is the carrier service.
- The *Carrier Cost Method* defines how to compute the carrier cost. By default
  there is only the *Product Price* method which takes the *List Price* of the
  *Product* as sale price and the *Cost Price* of the *Product* as purchase
  price.


Carrier Selection
*****************

A carrier selection defines the country of origin and destination where a
carrier can deliver the products.

- The *Sequence* is used to order the Carrier Selections.
- *Active* allows to disable a Carrier Selection.
- *From Country*  defines the Country of origin for this Carrier Selection.
  Empty value act as a wildcard.
- *To Country* defins the Country of destination for this Carrier Selection.
  Empty value act as a wildcard.
