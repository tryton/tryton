.. _topics-user_application:

================
User Application
================

User applications are a way to authenticate a user on a specific subset of URL
served by the Tryton server.

This subset of routes is created by using the
:ref:`user application decorator <topics-user_application_decorator>` on
those routes.

User Application Key
====================

Tryton provides an easy way to manage access to user application using keys per
named application.
A key is created with a ``POST`` request on the ``URL``
``/<database_name>/r/user/application/`` which returns the key.
The request must contain as data a JSON object with the keys:

``user``
   The user login.

``application``
   The name of the application.

After the creation, the key must be validated by the user from the preferences
of a Tryton client.

A key can be deleted with a ``DELETE`` request on the same ``URL``. The request
must contain as data a JSON object with the keys:

``user``
   The user login.

``key``
   The key to delete.

``application``
   The name of the application of the key.
