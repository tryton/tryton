.. _ref-tools:
.. module:: trytond.tools

Miscellaneous
=============

.. function:: file_open(name[, mode[, subdir[, encoding]]])

   Open the named file in subdir from the root directory.

.. function:: find_path(name[, subdir])

   Return the path of the named file in subdir from root directory.

.. function:: find_dir(name[, subdir])

   Return the path of the named directory in subdir from root directory.

.. function:: resolve(name)

   Resolve a dotted name to a global object.

.. method:: safe_join(directory, \*pathnames)

   Safely join zero or more untrusted path components to a base directory to
   avoid escaping the base directory.

.. function:: unescape_wildcard(string[, wildcards[, escape]])

   Return the string without the wild card escapes.

.. function:: is_full_text(value[, escape])

   Determine if the value can be used as full text search.

   This is the case when the value starts and ends with a ``%`` or does not
   contain any wild cards.

.. function:: sql_pairing(x, y)

   Return an SQL expression that pairs SQL integers x and y.

.. function:: firstline(text)

   Return first non-empty line of a text field.

.. function:: remove_forbidden_chars(value)

   Return a copy of the string with forbidden char from
   :class:`~trytond.model.fields.Char` replaced by space.
