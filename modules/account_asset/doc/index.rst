Account Asset Module
####################

The account_asset module adds the depreciation of fixed assets.

Asset
*****

An Asset defines how an asset is depreciated. It is mainly defined by:

- Product (of type "Assets").
- Journal.
- Value and Residual Value.
- Start and End Date.
- Depreciation Method:
  - Linear
- Frequency:
  - Monthly
  - Yearly
- Lines.

The asset can be in one of this states:

* Draft

  The depreciation lines can be created.

* Running

  The accounting moves of depreciation lines are posted.

* Closed

  The value of the asset has been completly depreciated.

A wizard "Create Assets Moves" allows to post all accounting move up to a date.

Asset Line
**********

An Asset Line defines for a date the value to depreciate.
