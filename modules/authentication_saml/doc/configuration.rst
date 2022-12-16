*************
Configuration
*************

The *Authentication SAML Module* introduces new authentication services from
settings in the ``[authentication_saml]`` section of the :doc:`configuration
file <trytond:topics/configuration>`.
The section lists the SAML service to setup with the string to display to the
user.
Each service can be configuration with a section named ``[authentication_saml
<service>]`` with the following options.

.. _config-authentication_saml.metadata:

``metadata``
============

The path to the metadata XML file of the IdP server.

.. _config-authentication_saml.config:

``config``
==========

The path of an optional configuration file using the `PySAML2 format
<https://pysaml2.readthedocs.io/en/latest/howto/config.html>`_

.. _config-authentication_saml.login:

``login``
=========

The name of the identity attribute that contains the Tryton login of the user.

The default value is ``uid``.

Example::

   [authentication_saml]
   test = SAMLTEST

   [authentication_saml test]
   metadata = /path/to/metadata.xml
   config = /path/to/config.py
   login = email
