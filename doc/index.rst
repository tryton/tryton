Sale Shipment Tolerance Module
##############################

The sale_shipment_tolerance modules adds under and over shipment tolerance on
the sale.
If the quantity of a sale line is under shipped but inside the tolerance
percentage, then the line will be considered as fully shipped and no back-order
will be created.
If the quantity of a sale line is over shipped more than the tolerance
percentage, then a warning is raised.
