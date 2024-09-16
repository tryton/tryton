*************
Configuration
*************

The *Inbound Email Module* uses values from settings in the ``[inbound_email]``
section of the :ref:`trytond:topics-configuration`.

.. _config-inboud_email.filestore:

``filestore``
=============

The ``filestore`` defines if the inbound emails are stored in the
:ref:`FileStore <trytond:ref-filestore>`.

The default value is: ``True``

.. _config-inbound_email.store_prefix:

``store_prefix``
================

The ``store_prefix`` contains the prefix to use with the :ref:`FileStore
<trytond:ref-filestore>`.

The default value is: ``None``

.. _config-inboud_email.max_size:

``max_size``
============

The maximum size in bytes of the inbound email request (zero means no limit).

The default value is: `trytond:config-request.max_size`
