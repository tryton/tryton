Sale Shipment Cost Module
#########################

The sale_shipment_cost module adds shipment cost for sale.

Two new fields are added to *Sale* and *Sale Configuration*:

- *Carrier*: The carrier used for the sale.
- *Shipment Cost Method*: The method used to compute the cost.

    - *On Order*: The cost will be invoiced once for the sale.
    - *On Shipment*: The cost will be invoiced for each shipments.
    - *None*: The cost will not be invoiced to the customer but added to the
      outgoing moves cost.

At the quotation if a carrier is selected a new line is appended with the
shipment cost but the added line can be modified when going back to draft.

Three new fields are added to *Customer Shipment*:

- *Carrier*: The carrier used for the shipment.
- *Cost*: The cost of the shipment.
- *Cost Currency*: The currency of the cost.
