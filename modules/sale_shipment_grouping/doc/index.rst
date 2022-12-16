Sale Shipment Grouping Module
#############################

The ``sale_shipment_grouping`` module adds an option to define how stock moves
generated from sales will be grouped.

A field is added to the *Party*:

- *Sale Shipment Grouping Method*: The method used when grouping stock moves.

If the Standard method is used, stock moves generated will be added to the
first matching shipment found. If no shipment matches sale attributes then a
new one will be created.
