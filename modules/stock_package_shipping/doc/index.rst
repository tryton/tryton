Stock Package Shipping Module
#############################

This module is the base module required to interact with shipping service
providers.

Carrier
*******

The Carrier model adds the following field:

- *Shipping Service*: The shipping service of the carrier.

This field is programmatically filled by the modules providing support for
shipping companies.

Package Type
************

The Package Type model has been added the following fields:

- *Length*: The length of the packages of this type
- *Length Unit*: The unit of measure of this length
- *Length Digits*: The precision of length
- *Height*: The height of the packages of this type
- *Height Unit*: The unit of measure of this height
- *Height Digits*: The precision of height
- *Width*: The width of the packages of this type
- *Width Unit*: The unit of measure of this width
- *Width Digits*: The precision of width

Package
*******

The Package model has been added the following fields:

- *Shipping Reference*: The shipping reference provided by the shipping service
- *Shipping Label*: The shipping label provided by the shipping service
- *Weight*: A function field computing the weight of the package with its
  content

Shipment Out
************

The Shipment Out model will check once in the Packed state if the shipment is a
valid shipment for the shipping service. He does that by calling a method that
is by convention named ``validate_packing_<shipping service>``.

Once a shipment is packed, the user can create the shipping for each packages
with the shipping service by clicking on the *Create Shipping* button. This
button triggers a wizard that is overridden in shipping service specific
modules. The starting state of the wizard is a ``StateTransition``. Its linked
method is overridden in shipping service modules in order to communicate with
the service.
