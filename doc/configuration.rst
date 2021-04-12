*************
Configuration
*************

The *Currency Module* uses some settings from the ``[currency]`` section of the
:doc:`configuration file <trytond:topics/configuration>`.

.. _config-currency.rate_decimal:

``rate_decimal``
=================

The ``rate_decimal`` setting defines how many decimal places are used when
storing currencies' `Rates <model-currency.currency.rate>`.

.. warning::

   Once the database has been created you cannot reduce this value, doing so
   will break your system's data integrity.
   Also if you want to increase this value you must also manually change it in
   the database `IR Configuration <trytond:model-ir.configuration>`.

The default value is: ``6``
