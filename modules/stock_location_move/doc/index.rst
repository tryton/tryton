Stock Location Move Module
##########################

The stock location move module allows to define some *Locations* as movable
(like palette).

Such locations can be moved using an *Internal Shipment*. The parent location
is changed for the destination location when the shipment is done. If there is
a transit location, the locations will be first moved to this one when shipped.
A reservation mechanism prevent to assign the same locations at the same time.

If a *Customer Shipment* or a *Supplier Return Shipment* empties a movable
location, it will automatically deactivate it.
