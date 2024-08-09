*************
Configuration
*************

The *Notification Email Module* uses values from the settings in the
``[notification_email]`` section of the :ref:`trytond:topics-configuration`.

.. note::

   To send email, the general :ref:`trytond:config-email` section must also be
   configured.

.. _config-notification_email.from:

``from``
========

This defines the default ``From`` to use for sending emails.
If it is not set the value of :ref:`trytond:config-email.from` will be used.
