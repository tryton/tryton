Stock Package Shipping DPD Module
#################################

The Stock Package Shipping DPD module allows you to generate the DPD label
using the DPD webservices.
DPD has many different web services, the module supports:

- `public-ws.dpd.com`

Carrier Credential
******************

This model allows to define the credential used to connect the the DPD API.
The credentials will be automatically retrieved based on the company of the
Shipment.

- *Company*: The company for which those credentials are valid
- *User ID*: The User ID provided by DPD.
- *Password*: The Password used to access the DPD API.
- *Server*: Are those credentials used for accessing the Testing or the
  Production server.
