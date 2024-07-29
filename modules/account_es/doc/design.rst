******
Design
******

The *Spanish Account Module* introduces the following concepts:

.. _wizard-account.reporting.aeat:

AEAT
====

The *AEAT* wizard can generate the following AEAT files:

   * `Model 111`_
   * `Model 115`_
   * `Model 303`_

.. seealso::

   The AEAT wizard can be run by opening the main menu item:

      |Financial --> Reporting --> Print AEAT|__

      .. |Financial --> Reporting --> Print AEAT| replace:: :menuselection:`Financial --> Reporting --> Print AEAT`
      __ https://demo.tryton.org/wizard/account.reporting.aeat

.. _model-account.reporting.vat_list_es:

Spanish VAT List
================

The *Spanish VAT List* provides the :abbr:`VAT (Value Added Tax)` amount
invoiced for a given year.

.. seealso::

   The Spanish VAT List can be found by opening the main menu item:

      |Financial --> Reporting --> Spanish VAT List|__

      .. |Financial --> Reporting --> Spanish VAT List| replace:: :menuselection:`Financial --> Reporting --> Spanish VAT List`
      __ https://demo.tryton.org/model/account.reporting.vat_list_es;context_model=account.reporting.vat_list_es.context

Reports
-------

.. _report-account.reporting.aeat347:

AEAT Model 347
^^^^^^^^^^^^^^

The *AEAT Model 347* report generates the `Model 347`_ text file.

.. _model-account.reporting.es_ec_operation_list:

EC Operation List
=================

The *EC Operation List* provides the details of purchases to other :abbr:`VAT
(Value Added Tax)` registered companies in other :abbr:`EU (European Union)`
countries.

.. seealso::

   The EC Operation List can be found by opening the main menu item:

      |Financial --> Reporting --> EC Operation List|__

      .. |Financial --> Reporting --> EC Operation List| replace:: :menuselection:`Financial --> Reporting --> EC Operation List`
      __ https://demo.tryton.org/model/account.reporting.es_ec_operation_list;context_model=account.reporting.es_ec_operation_list.context

Reports
-------

.. _report-account.reporting.aeat349:

AEAT Model 349
^^^^^^^^^^^^^^

The *AEAT Model 349* report generates the `Model 349`_ text file.

.. _model-account.reporting.vat_book_es:

Spanish VAT Book
================

The *Spanish VAT Book* computes the records to generate the `register book of
issued or received invoices and capital goods
<https://sede.agenciatributaria.gob.es/Sede/en_gb/iva/libros-registro.html>`_.

.. seealso::

   The Spanish VAT Book can be found by opening the main menu item:

      |Financial --> Reporting --> Spanish VAT Book|__

      .. |Financial --> Reporting --> Spanish VAT Book| replace:: :menuselection:`Financial --> Reporting --> Spanish VAT Book`
      __ https://demo.tryton.org/model/account.reporting.vat_book_es;context_model=account.reporting.vat_book_es.context

Reports
-------

.. _report-account.reporting.aeat.vat_book:

VAT Book
^^^^^^^^

The *VAT Book* report generate a :abbr:`CSV (Comma-separated Values)` file from
the *VAT Book* entries.

.. _Model 111: https://sede.agenciatributaria.gob.es/Sede/en_gb/procedimientoini/GH01.shtml
.. _Model 115: https://sede.agenciatributaria.gob.es/Sede/en_gb/procedimientoini/GH02.shtml
.. _Model 303: https://sede.agenciatributaria.gob.es/Sede/en_gb/procedimientoini/G414.shtml
.. _Model 347: https://sede.agenciatributaria.gob.es/Sede/en_gb/procedimientoini/GI27.shtml
.. _Model 349: https://sede.agenciatributaria.gob.es/Sede/en_gb/procedimientoini/GI28.shtml
