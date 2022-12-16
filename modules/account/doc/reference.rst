*************
API Reference
*************

Periods
=======

.. class:: ActivePeriodMixin

   This mixin_ makes it easy to create a :class:`~trytond:trytond.model.Model`
   which is active between a start and end date.
   The date range, `Periods <model-account.period>`, or
   `Fiscal Years <model-account.fiscalyear>` that are set in the context are
   used to determine if a particular record should be considered active, or
   not.

.. class:: PeriodMixin

   This mixin_ provides a start and end date to classes that inherit it.
   It also limits any parent or child fields of the class to the same
   `Company <company:model-company.company>` and to dates in the same period.

Taxation
========

.. class:: TaxableMixin

   This is a mixin_ that helps create classes that need to calculate
   `Taxes <model-account.tax>`, tax lines, and tax and base amounts from
   a list of taxable lines.

.. _mixin: https://en.wikipedia.org/wiki/Mixin

*********************
Development Reference
*********************

The *Account Module* includes minimal charts of accounts for many languages.
The :abbr:`XML (eXtensible Markup Language)` files that contain the localised
charts of account are all generated from the same source XML file.
The :file:`localize.xsl` :abbr:`XSLT (XML Stylesheet Language Transform)` file
defines how the source XML file is transformed into a localised chart of
accounts.

To output a localised chart of accounts for language ``<lang>`` run:

.. code-block:: bash

   xsltproc --stringparam lang <lang> localize.xsl minimal_chart.xml
