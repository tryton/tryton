LDAP Authentication Module
##########################

The LDAP authentication module allows to authenticate users via a LDAP server.

The configuration of the LDAP connection is set in the `ldap_authentication`
section.

To be activated, the `ldap` method must be added to the `authentications`
methods list of the `session` section of the configuration.

Configuration
*************

uri
---

The LDAP URL to use to connect to the server following the :rfc:`2255`.
It is extended to support `SSL
<https://en.wikipedia.org/wiki/Secure_Sockets_Layer>`_ and `STARTTLS
<https://en.wikipedia.org/wiki/STARTTLS>`_.
The available protocols are:

   - ``ldap``: simple LDAP
   - ``ldap+tls``: LDAP with STARTTLS
   - ``ldaps``: LDAP with SSL


bind_pass
---------

The LDAP password used to bind if needed.

uid
---

The UID Attribute for authentication (default is `uid`).

create_user
-----------

A boolean to create user if not in the database.
