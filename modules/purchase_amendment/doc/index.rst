Purchase Amendment Module
#########################

The purchase amendment module allows you to change purchases that are being
processed and keep track of the changes.
An amendment is composed of action lines which can:

* Recompute taxes (if the supplier tax rules or product taxes have changed)

* Change the payment term

* Change the party and the address

* Change the warehouse

* Change a purchase line:

    * the product (for one with the same UoM category)

    * the quantity and unit of measure

    * the unit price

    * the description

When the amendment is validated the purchase is updated and given a new
revision. Generated documents (like moves and invoices) that are still in a
draft state are replaced with new ones based on the new values.
