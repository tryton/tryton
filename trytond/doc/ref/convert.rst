.. _ref-convert:
.. module:: trytond.convert

=======
Convert
=======

The ``convert`` module provides a way to import records from XML files.


import_xml
----------

.. function:: import_xml(xml, module)

Imports the records from ``xml`` into the database as if they were defined in
``module``.
Those records are not store in the Model Data table.
``xml`` can be a :py:class:`string <str>`, a :py:class:`bytes <bytes>` or a
file object.
