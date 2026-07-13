Stock Package Shipping DPD Module
#################################

The Stock Package Shipping DPD module allows you to generate the DPD label
using the `DPD webservices <https://esolutions.dpd.com/>`_.
DPD has many different web services, the module supports:

- LoginService 2.0
- ShipmentService 4.5

Carrier Credential
******************

This model allows to define the credential used to connect the DPD API.
The credentials will be automatically retrieved based on the company of the
Shipment.

- *Company*: The company for which those credentials are valid
- *User ID*: The User ID provided by DPD.
- *Password*: The Password used to access the DPD API.
- *Server*: Are those credentials used for accessing the Testing or the
  Production server.

Carrier
*******

The Carrier model is extended with the following fields:

- *Product*: The DPD product requested.
- *Printer Language*: The type of file used for the label sent by DPD
- *Paper Format*: The format of the label sent by DPD
