*************
Configuration
*************

The *EDocument Peppol Peppyrus Module* uses values from settings in the
``[edocument_peppol_peppyrus]`` section of the
:ref:`trytond:topics-configuration`.

.. _config-edocument_peppol_peppyrus.max_size:

``max_size``
============

The maximum size in bytes of the Peppyrus Webhook request (zero means no
limit):

The default value is: `trytond:config-request.max_size`

.. _config-edocument_peppol_peppyrus.requests_timeout:

``requests_timeout``
====================

The ``requests_timeout`` defines the time in seconds to wait for the Peppyrus
APIs answer before failing.

The default value is: ``300``
