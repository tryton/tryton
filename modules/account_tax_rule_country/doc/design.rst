******
Design
******

The *Account Tax Rule Country Module* extends the following concepts:

.. _model-account.tax.rule:

Tax Rule
========

When the *Account Tax Rule Country Module* is activated, the *Tax Rule* gains
additional criteria for the origin and destination `Country
<country:model-country.country>` and `Subdivision
<country:model-country.subdivision>` to match against.

The countries and subdivisions are taken from the origin document that applies
the tax rule:

- `Sale <sale:model-sale.sale>`:

  - The country and subdivision of origin are taken from the `Warehouse
    <stock:concept-stock.location.warehouse>` address.
  - The country and subdivision of the destination are taken from the shipping
    address.

- `Purchase <purchase:model-purchase.purchase>`:

  - The country and subdivision of origin are taken from the invoice address.
  - The country and subdivision of the destination are taken from the warehouse
    address.

- Stock Consignment `Move <stock:model-stock.move>`:

  - The country and subdivision of origin are taken from the warehouse address
    of the `Location <stock:model-stock.location>` or the delivery address of
    the `Customer Return Shipment <stock:model-stock.shipment.out.return>`.
  - The country and subdivision of the destination are taken from the warehouse
    address of the location or the delivery address of `Customer Shipment
    <stock:model-stock.shipment.out>`.

.. seealso::

   The `Tax Rule <account:model-account.tax.rule>` concept is introduced by the
   :doc:`Account Module <account:index>`.
