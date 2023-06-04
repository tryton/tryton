*****
Setup
*****

.. _Setting up UPS credentials:

Setting up UPS credentials
==========================

The *Stock Package Shipping UPS Module* needs credentials to access the APIs by
`creating an Application <https://developer.ups.com/get-started>`_.
The Application needs to have at least access to:

   * Shipping

You need to copy the *Client ID* and *Client Secret* that have been generated.

When setting the `UPS Credential <model-carrier.credential.ups>`, you must fill
the "Account Number" with the same account the application was created and the
"Client ID" and "Client Secret" with the copied values.

.. tip::

   Try first with the "Testing" server before swicth to "Production".
