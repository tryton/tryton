******
Design
******

The *EDocument Peppol Peppyrus Module* extends the following concepts:

.. _model-edocument.peppol.service:

Service
=======

When the *EDocument Peppol Peppyrus Module* is activated, the *Peppol Service*
gains a new :guilabel:`Service` option for *Peppyrus* and a property to store
the :guilabel:`API Key` to communicate with the service.

.. note::
   A `scheduled task <trytond:model-ir.cron>` is run every hour to fetch new
   messages in the :guilabel:`Inbox`.

.. seealso::

   The `Service <edocument_peppol:model-edocument.peppol.service>` concept is
   introduced by the :doc:`EDocument Peppol Module <edocument_peppol:index>`.
