Stock Package Shipping UPS Module
#################################

The Stock Package Shipping UPS module allows you to generate the UPS labels per
package using the UPS webservices.

The credential for the webservice is specified by the following fields:

UPS Carrier Credential
**********************

This model allows to define the credential used to connect the UPS API.
The credentials used to connect to the UPS API will be automatically retrieved
based on the company of the Shipment.

- *Company*: The company for which those credentials are valid
- *User ID*: The User ID provided by UPS.
- *Password*: The Password used to access the MyUPS Portal.
- *Account Number*: The account number UPS assigned to you when you requested the
  API credentials (also known as the Shipper Number).
- *License*: The License number UPS assigned to you when you requested the API
  credentials
- *Server*: Are those credentials used for accessing the Testing or the
  Production server of UPS.
- *Use Metric*: Use Metric units when communicating with the UPS webservice.

Carrier
*******

The Carrier model is extended with the following fields:

- *Service Type*: The UPS service type requested
- *Label Image Format*: The Image Format used for the label sent by UPS
- *Label Image Height*: The Height of the label sent by UPS.

Package Type
************

The Package Type model is extended with the following field:

- *UPS Code*: The UPS Code of the package.
