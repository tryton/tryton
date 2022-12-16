Sale Amendment Module
#####################

The sale amendment module allows you to change sales that are being processed
and keep track of the changes.
An amendment is composed of action lines which can:

* Recompute taxes (if the customer tax rules or product taxes have changed).

* Change the payment term

* Change parties and addresses

* Change the warehouse

* Change a sale line:

    * the product (for one with the same UoM category)

    * the quantity and unit of measure

    * the unit price

    * the description

When the amendment is validated the sale is updated and given a new revision.
Generated documents (like shipments and invoices) that are still in a draft
state are replaced with new ones based on the new values.
