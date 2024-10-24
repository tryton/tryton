.. _ref-report:
.. module:: trytond.report

Report
======

A report generates printable documents from
:class:`~trytond.model.ModelStorage` records.

There is also a more :ref:`practical introduction into reports
<topics-reports>`.

.. class:: Report()

   This is the base class for all reports.

Class attributes are:

.. attribute:: Report.__name__

   The unique name used to reference the report throughout the platform.

Class methods are:

.. classmethod:: Report.__setup__()

   Setup the class before adding it to the :class:`~trytond.pool.Pool`.

.. classmethod:: Report.__post_setup__()

   Setup the class after adding it to the :class:`~trytond.pool.Pool`.

.. classmethod:: Report.__register__(module_name)

   Registers the report.

.. classmethod:: Report.check_access(action, model, ids)

   Verifies if the :attr:`~trytond.transaction.Transaction.user` is allowed to
   execute the report.

.. classmethod:: Report.header_key(record[, data])

   Returns a tuple of keys, composed of couples of name and record value, used
   to group document with the same header.
   ``data`` is the dictionary passed to :meth:~Report.execute`.

.. classmethod:: Report.execute(ids, data)

   Executes the report for the :class:`~trytond.model.ModelStorage` instances
   with the ``ids`` and returns a tuple containing the report type, the content,
   a boolean to indicate direct printing and the report name.
   ``data`` is a dictionary that will be available in the evaluation context of
   the report.

.. classmethod:: Report.get_context(records, header, data)

   Returns a dictionary with the evaluation context of the report template.
   The context is filled by default with the keys:

      - ``header``
      - ``data``
      - :attr:`~trytond.transaction.Transaction.context`
      - :attr:`~trytond.transaction.Transaction.user`
      - ``records``
      - ``record`` (containing the first ``records``)
      - :meth:`~Report.format_date`
      - :meth:`~Report.format_datetime`
      - :meth:`~Report.format_timedelta`
      - :meth:`~Report.format_currency`
      - :meth:`~Report.format_number`
      - :meth:`~Report.format_number_symbol`
      - :py:mod:`datetime`
      - :meth:`~Report.barcode`
      - :meth:`~Report.qrcode`
      - ``set_lang``
      - :meth:`~trytond.i18n.gettext` as ``msg_gettext``
      - :meth:`~trytond.i18n.ngettext` as ``msg_ngettext``

.. classmethod:: Report.render(report, report_context)

   Returns the content of the `Report <model-ir.action.report>` rendered by the
   templating engine.
   And add ``gettext`` and ``ngettext`` to the evaluation context for
   translatable reports.

.. classmethod:: Report.convert(report, data, [timeout[, retry]])

   Converts the report content ``data`` into the format defined by the `Report
   <model-ir.action.report>`.

.. classmethod:: Report.format_date(value[, lang[, format]])

   Returns the formatted :py:class:`~datetime.date`.

.. classmethod:: Report.format_datetime(value[, lang[, format[, timezone]]])

   Returns the formatted :py:class:`~datetime.datetime`.

.. classmethod:: Report.format_timedelta(value[, converter[, lang]])

   Returns the formatted :py:class:`~datetime.timedelta`.

.. classmethod:: Report.format_currency(value, lang, currency[, symbol[, grouping[, digits]]])

   Returns the formatted numeric value.

.. classmethod:: Report.format_number(value, lang[, digits[, grouping[, monetary]]])

   Returns the formatted numeric value.

.. classmethod:: Report.format_number_symbol(value, lang, symbol[, digits[, grouping[, monetary]]])

   Returns the numeric value formatted using the
   :class:`~trytond.model.SymbolMixin` instance.

.. classmethod:: Report.barcode(name, code[, size[, \*\*kwargs]])

   Returns named barcode image for the ``code``, the mimetype and the size.
   The optional keyword arguments are the same as
   :func:`~trytond.tools.barcode.generate_svg`.

.. classmethod:: Report.qrcode(code[, size[, \*\*kwargs]])

   Returns the QRCode image for the ``code``, the mimetype and the size.
   The optional keyword arguments are the sames as
   :func:`~trytond.tools.qrcode.generate_svg`.

Email
=====

.. function:: get_email(report, record, languages)

   Returns the :py:class:`~email.message.EmailMessage` and title using the
   `Report <model-ir.action.report>` rendered for the
   :class:`~trytond.model.ModelStorage` record for each language.
