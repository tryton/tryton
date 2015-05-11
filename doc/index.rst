Sale Extra
##########

The sale_extra module allows to add extra line on sale based on criteria.

The extra products are added when the sale goes into quotation but the added
lines can be modified when going back to draft.

The criteria are defined by the *Sale Extras* of the *Price List*.

Sale Extra
**********

Each matching *Sale Extra* is evaluated to add an extra line.
The criteria are the fields:

- *Price List*
- *Start/End Date*
- *Sale Amount*: If untaxed sale amount is greater or equal
  (in the price list company currency).

Sale Extra Line
***************

Once a *Sale Extra* is selected, its first line that match the line's criteria
is used to setup the extra line.
The criteria are the fields:

- *Sale Amount*: If the untaxed sale amount is greater or equal
  (in the price list company currency).

The sale line is setup using the fields:

- *Product*: The product to use on the sale line.
- *Quantity*: The quantity to set on the sale line (in the *Unit*).
- *Unit*: The unit of measure to use.
- *Free*: Set unit price of the sale line to zero, otherwise to the sale price.
