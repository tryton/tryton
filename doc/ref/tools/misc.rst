.. _ref-tools:
.. module:: trytond.tools

Miscellaneous
=============

.. method:: file_open(name[, mode[, subdir[, encoding]]])

   Open the named file in subdir from the root directory.

.. method:: find_path(name[, subdir])

   Return the path of the named file in subdir from root directory.

.. method:: find_dir(name[, subdir])

   Return the path of the named directory in subdir from root directory.

.. method:: resolve(name)

   Resolve a dotted name to a global object.

.. method:: unescape_wildcard(string[, wildcards[, escape]])

   Return the string without the wild card escapes.

.. method:: is_full_text(value[, escape])

   Determine if the value can be used as full text search.

   This is the case when the value starts and ends with a ``%`` or does not
   contain any wild cards.

.. method:: sql_pairing(x, y)

   Return an SQL expression that pairs SQL integers x and y.

.. method:: firstline(text)

   Return first non-empty line of a text field.

.. method:: remove_forbidden_chars(value)

   Return a copy of the string with forbidden char from
   :class:`~trytond.model.fields.Char` replaced by space.
