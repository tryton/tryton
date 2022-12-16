.. _ref-tools:
.. module:: trytond.tools

=============
Miscellaneous
=============

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
