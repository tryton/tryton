Sale Promotion
##############

The sale_promotion module allows to apply promotions on sale based on criteria.

The promotion is applied by changing the unit price of the affected lines when
the sale goes into quotation but the unit price is restored when going back to
draft.

Sale Promotion
**************

Each matching *Sale Promotion* is considered for application but only those who
reduces the unit price of the lines are really applied.
The criteria are the fields:

- *Company*: The company should be the same as the sale.
- *Price List*: The sale price list.
- *Start Date*/*End Date*: The period for which the promotion is valid.
- *Quantity*: The sum quantity of the sale lines which have the same *Unit*.
- *Products*: The list of products to apply the promotion.
- *Categories*: The list of product categories to apply the promotion.

The new unit price is computed by the field *Formula*.
