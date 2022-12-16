Account Dunning Fee Module
##########################

The account_dunning_fee module allows to generate accounting moves as fees when
processing dunning which are at a level with a *Fee* defined.

The accounting move debit the fee amount from the same account as the due line
and credit the revenue account of the product.  Only one move is created per
dunning and level.

Fee
***

A *Fee* defines the parameters to apply the fee:

- Name: The string that will be used as account move description.
- Product: The service product that represent the fee.
- Journal: The journal on which the move will be posted.
- Compute Method:

  - List Price: The list price of the product.
  - Percentage: A percentage of the due amount.
