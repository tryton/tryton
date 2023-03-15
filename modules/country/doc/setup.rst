*****
Setup
*****

When the *Country Module* is activated it does not create any country,
subdivision or postal code records.
You do this using the provided scripts.

.. _Loading and updating countries and subdivisions:

Loading and updating countries and subdivisions
===============================================

The :command:`trytond_import_countries` script loads and updates Tryton with
the `ISO 3166`_ list of `Countries <model-country.country>` and
`Subdivisions <model-country.subdivision>`.

You run it with:

.. code-block:: sh

   trytond_import_countries -c trytond.conf -d <database>

.. _ISO 3166: https://en.wikipedia.org/wiki/ISO_3166

.. _Loading and updating postal codes:

Loading and updating postal codes
=================================

You can use the :command:`trytond_import_postal_codes` script to load and update
the `Postal Codes <model-country.postal_code>` in Tryton from the `GeoNames
Database`_.
It is run with:

.. code-block:: console

   $ trytond_import_postal_codes -c trytond.conf -d <database> <two_letter_country_code>

.. _GeoNames Database: https://www.geonames.org/
