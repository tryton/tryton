.. _ref-config:
.. module:: trytond.config

======
Config
======

The config gives access to the configuration.

.. contents::
   :local:
   :backlinks: entry
   :depth: 1

.. function:: get_hostname(netloc)

   Returns the hostname from the network location/authority of :abbr:`URI
   (Uniform Resource Identifier)`.

.. function:: get_port(netloc)

   Returns the port from the network location/authority of :abbr:`URI (Uniform
   Resource Identifier)`.

.. function:: split_netloc(netloc)

   Returns the couple hostname and port from the network location/authority of
   :abbr:`URI (Uniform Resource Identifier)`.

.. function:: parse_listen(value)

   Yields couples of hostname and port from the comma separated list of network
   location/authority of :abbr:`URI (Uniform Resource Identifier)`.

.. function:: parse_uri(uri)

   Parses a :abbr:`URI (Uniform Resource Identifier)`, returning a namedtuple.

.. function:: update_etc([configfile])

   Tries to update the configuration with the file or list of files and returns
   the filenames which were successfully parsed.

.. function:: has_section(section)

   Indicates whether the named section is present in the configuration.

.. function:: add_section(section)

   Adds the named section.

.. function:: remove_section(section)

   Removes the named section.

.. function:: set(section, option[, value])

   Set the given option to the specified value.

.. function:: get(section, option[, default])

   Get an option value for the named section. If the key is not found the
   default value is provided.

.. function:: getint(section, option[, default])

   A convenience method which coerces the option in the specified section to an
   :py:class:`int`.
   See :func:`get`.

.. function:: getfloat(section, option[, default])

   A convenience method which coerces the option in the specified section to a
   :py:class:`float`.
   See :func:`get`.

.. function:: getboolean(section, option[, default])

   A convenience method which coerces the option in the specified section to a
   :py:class:`bool`.
   See :func:`get`.
