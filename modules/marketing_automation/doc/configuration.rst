*************
Configuration
*************

The *Marketing Automation Module* uses some settings from the ``[marketing]``
section of the :doc:`configuration file <trytond:topics/configuration>`.

.. _config-marketing.email_from:

``email_from``
==============

The default email adresse used as ``From`` when sending email.

The default value is empty.

.. _config-marketing.automation_base:

``automation_base``
===================

The base URL without any path for the unsubscribe URL and the tracking image.

The default value is constricted using the configuration ``hostname``.
