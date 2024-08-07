*************
API Reference
*************

Resources
=========

.. module:: trytond.ir.resource

.. class:: ResourceAccessMixin

   This mixin_ adds a ``resource`` :class:`~trytond.model.fields.Reference`
   field and applies the same access right as the resource to the
   :class:`~trytond.model.ModelStorage`.

.. class:: ResourceMixin

   This mixin_ extends the :class:`ResourceAccessMixin` to add some metadata
   fields and the option to copy the record using :meth:`resource_copy`.

.. method:: resource_copy(resource, name, string)

   Returns a mixin_ that adds the named :class:`~trytond.model.fields.One2Many`
   to the ``resource`` :class:`~trytond.model.ModelStorage`.
   The mixin also adds a ``copy_resources_to(target)`` instance method that
   copies the resource records to the ``target``.

Attachments
===========

.. module:: trytond.ir.attachment

.. class:: AttachmentCopyMixin

   A mixin_ setup by the :meth:`~trytond.ir.resource.resource_copy` for the
   `Attachments <model-ir.attachment>`.

Notes
=====

.. module:: trytond.ir.note

.. class:: NoteCopyMixin

   A mixin_ setup by the :meth:`~trytond.ir.resource.resource_copy` for the
   `Notes <model-ir.note>`.

Language
========

.. module:: trytond.ir.lang

.. class:: Language

.. method:: Language.get([code])

   Returns the language instance for the ``code`` or the
   :attr:`~trytond.transaction.Transaction.language`.

.. method:: Language.format(percent, value[, grouping[, monetary[, \*\*additional]]])

   Formats the ``value`` according to the language by substitution of the
   ``%?`` specifier.

.. method:: Language.currency(val, currency[, symbol[, grouping[, digits]]])

   Formats the numeric ``value`` according to the language and the currency.

.. method:: Language.strftime(value[, format])

   Formats the :py:class:`~datetime.date` or :py:class:`~datetime.datetime`
   according to the language.

.. method:: Language.format_number(value[, digits[, grouping[, monetary]]])

   Formats the number ``value`` according to the language.

.. method:: Language.format_number_symbol(value, symbol[, digits[, grouping]])

   Formats the number ``value`` with the :class:`~trytond.model.SymbolMixin`
   instance according to the language.

.. _HTML Editor:

HTML Editor
===========

A route is registered to allow HTML :class:`~trytond.model.fields.Text` fields
to be edited using a web editor:

   - ``GET`` ``/<database_name>/ir/html/<model>/<record>/<field>``
     Returns the web page containing the editor with:

      ``model`` is the name of the :class:`~trytond.model.ModelStorage`.
      ``record`` is the :class:`~trytond.model.Model.id` of the record.
      ``field`` is the name of the :class:`~trytond.model.fields.Text` field.

   - ``POST`` ``/<database_name>/ir/html/<model>/<record>/<field>``
     Save the ``text`` value in the form with:

      ``model`` is the name of the :class:`~trytond.model.ModelStorage`.
      ``record`` is the :class:`~trytond.model.Model.id` of the record.
      ``field`` is the name of the :class:`~trytond.model.fields.Text` field.


.. _Download CSV Data:

Download CSV Data
=================

A route is registered to download records as a CSV file:

   - ``GET`` ``/<database_name>/data/<model>``
     Returns a CSV file for the records of ``model`` using the parameters:

      ``l`` is the language.
      ``d`` is a JSON encoded domain.
      ``c`` is a JSON encoded context.
      ``s`` is an integer to limit the number of records.
      ``p`` is the offset to apply to the list of records.
      ``o`` is a list of fields and orders separated by ``,``.
      ``f`` is a list of field names.
      ``enc`` is the encoding with ``UTF-8`` as default.
      ``dl`` is the CSV delimiter.
      ``qc`` is the quoting char.
      ``h`` is a boolean integer whether to include the header or not.
      ``loc`` is a boolean integer whether to use locale format or not.

.. _Fetch Avatar:

Fetch Avatar
============

A route is registered from which an `Avatar <model-ir.avatar>` can be downloaded:

   - ``GET`` ``/avatar/<database_name>/<uuid>``
     Returns the avatar using ``s`` parameter for the size and with:

      ``database_name`` is the name of the database encoded in base64.
      ``uuid`` is the UUID of the avatar.

.. _mixin: https://en.wikipedia.org/wiki/Mixin
