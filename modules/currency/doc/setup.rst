*****
Setup
*****

On activation, the module does not create any currency records.
It is possible to load them from the ISO database.

.. _Loading and updating currencies:

Loading and updating currencies
===============================

There is a script called :command:`trytond_import_currencies` that creates and
updates `Currencies <model-currency.currency>`.

You can run it with:

.. code-block:: console

   $ trytond_import_currencies -c trytond.conf -d <database>
