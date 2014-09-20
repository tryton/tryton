LDAP Authentication Module
##########################

The LDAP authentication module allows to authenticate users via a LDAP server.

The configuration of the LDAP connection is set in the `ldap_authentication`
section.

Configuration
*************

uri
---

The LDAP URL to use to connect to the server following the RFC-2255_.

bind_pass
---------

The LDAP password used to bind if needed.

active_directory
----------------

A boolean to set if the LDAP server is an Active Directory.

uid
---

The UID Attribute for authentication (default is `uid`).

create_user
-----------

A boolean to create user if not in the database.

.. _RFC-2255: http://tools.ietf.org/html/rfc2255
