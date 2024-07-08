*************
Configuration
*************

The *Web user Module* uses values from settings in different sections of
the :ref:`trytond:topics-configuration`.

``[web]``
*********

.. _config-web.reset_password_url:

``reset_password_url``
======================

The ``reset_password_url`` defines the URL for the page where web users can
reset their password.
The parameters ``email`` and ``token`` are added automatically.

``email_validation_url``
========================

The ``email_validation_url`` defines the URL used to validate a web user's
email address.
The parameter ``token`` is added automatically.

``[session]``
*************

``web_timeout``
===============

The duration in seconds that a web user session remains valid.

The default value is: ``2592000`` (30 days)

``web_timeout_reset``
=====================

The time in seconds until the password reset expires.

The default value is ``86400`` (1 day)
