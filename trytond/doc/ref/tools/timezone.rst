.. _ref-tools-timezone:
.. module:: trytond.tools.timezone

timezone
========

.. function:: get_tzinfo(zoneid)

   Get a class representing a IANA time zone specified by the string ``zoneid``.

.. function:: available_timezones()

   Return a set of all the valid IANA keys available.

.. attribute:: UTC

   The UTC :py:class:`datetime.tzinfo` instance.

.. attribute:: SERVER

   The server timezone :py:class:`datetime.tzinfo` instance.

   Tryton tests the environment variables ``TRYTOND_TZ`` and ``TZ`` in this
   order to select to IANA key to use.
   If they are both empty, it defaults to ``UTC``.
