Stock Lot Unit Module
#####################

The `stock_lot_unit` module allows to define a unit and quantity on stock lot.

Lots with unit have the following properties:

    - no shipment may contain a summed quantity for a lot greater than the
      quantity of the lot.
    - no move related to a lot with a unit may concern a quantity greater than
      the quantity of the lot.

The *Lot Unit* field is added to the product. This defines the unit to set on
new lot.
