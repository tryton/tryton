*************
Configuration
*************

The *LDAP Authentication Module* uses values from settings in the
``[ldap_authentication]`` section of the :doc:`configuration file
<trytond:topics/configuration>`.

To be activated, the ``ldap`` method must be added to the `authentications
<trytond:config-session.authentications>` methods list in the `session
<trytond:config-session>` section of the configuration file.

.. _config-ldap_authentication.uri:

``uri``
=======

The LDAP URL to use to connect to the server following :rfc:`2255`.
It is extended to support `SSL
<https://en.wikipedia.org/wiki/Secure_Sockets_Layer>`_ and `STARTTLS
<https://en.wikipedia.org/wiki/STARTTLS>`_.
The available protocols are:

   - ``ldap``: simple LDAP
   - ``ldap+tls``: LDAP with STARTTLS
   - ``ldaps``: LDAP with SSL

.. _config-ldap_authentication.uid:

``uid``
=======

The LDAP attribute holding the login name of the corresponding user in Tryton.

The default value is: ``uid``

.. _config-ldap_authentication.bind_pass:

``bind_pass``
=============

The LDAP password used to bind to the server if needed.

.. _config-ldap_authentication.create_user:

``create_user``
===============

Determines whether a new user is automatically created in Tryton when LDAP
authentication succeeds and the user doesn't already exist.
When ``False`` only users that already exist in Tryton are able to login,
but when set to ``True`` any LDAP user can login.

The default value is: ``False``
