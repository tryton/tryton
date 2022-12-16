Account Asset Module
####################

The account_asset module adds the depreciation of fixed assets.

Asset
*****

An Asset defines how an asset is depreciated. It is mainly defined by:

- Product (of type "Assets").
- Journal.
- Value, Depreciated Amount and Residual Value.
- Start and End Date.
- Depreciation Method:

  - Linear

- Frequency:

  - Monthly
  - Yearly (using fixed year of 365 days)

- Lines.

The asset can be in one of this states:

* Draft

  The depreciation lines can be created.

* Running

  The accounting moves of depreciation lines are posted.

* Closed

  The value of the asset has been completely depreciated.

A wizard "Create Assets Moves" allows to post all accounting move up to a date.

The day and the month when the move will posted are defined on the accounting
configuration.

Asset Line
**********

An Asset Line defines for a date the value to depreciate.
