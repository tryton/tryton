.. _model-ir.calendar.month:

Calendar Month
==============

The *Calendar Month* stores each month of the `Gregorian calendar
<https://en.wikipedia.org/wiki/Gregorian_calendar>`_.

.. note::
   Its goal is to provide a target for :class:`~trytond.model.fields.Many2One`
   fields with localized month names.

.. _model-ir.calendar.day:

Calendar Day
============

The *Calendar Day* stores each day of the `week
<https://en.wikipedia.org/wiki/Week>`_.

.. note::
   Its goal is to provide a target for :class:`~trytond.model.fields.Many2One`
   fields with localized week day names.
