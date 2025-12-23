*************
API Reference
*************

.. _Peppyrus Webhook:

Peppyrus Webhook
================

The *EDocument Peppol Peppyrus MOdule* defines routes to receive the Peppyrus'
webhooks:

   - ``POST`` ``/<database_name>/edocument_peppol_peppyrus/<identifier>/in``:
      Stores the payload message.

      ``identifier`` is the Peppyrus identifier of the `Service
      <model-edocument.peppol.service>`.

   - ``POST`` ``/<database_name>/edocument_peppol_peppyrus/<identifier>/out``:
      Update the status of the payload message.

      ``identifier`` is the Peppyrus identifier of the `Service
      <model-edocument.peppol.service>`.
