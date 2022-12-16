*************
API Reference
*************

.. module:: trytond.modules.currency.fields

Monetary field
==============

.. class:: Monetary(string[, currency[, \**options]])

A subclass of :class:`~trytond:trytond.model.fields.Numeric` used to store monetary values.

.. attribute:: Monetary.currency

   The name of the :class:`~trytond:trytond.model.fields.Many2One` field which
   stores the currency used to display the symbol.
