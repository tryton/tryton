******
Design
******

The *Country Module* introduces the following concepts:

.. _model-country.organization:

Organization
============

The *Organization* represents an international organization of `Countries
<model-country.country>`.

.. seealso::

   Organizations can be found under the main menu entry:

      |Administration --> Countries --> Organizations|__

      .. |Administration --> Countries --> Organizations| replace:: :menuselection:`Administration --> Countries --> Organizations`
      __ https://demo.tryton.org/model/country.organization


.. _model-country.region:

Region
======

The *Region* represents a geographical region that groups `Countries <model-country.country>`.
The main usage is for reporting and statistics.

The `UN M49 <https://unstats.un.org/unsd/methodology/m49/>`_ methodology and
codes are used when `Loading and updating countries and subdivisions`.

.. seealso::

   Regions can be found under the main menu entry:

      |Administration --> Countries --> Regions|__

      .. |Administration --> Countries --> Regions| replace:: :menuselection:`Administration --> Countries --> Regions`
      __ https://demo.tryton.org/model/country.region

.. _model-country.country:

Country
=======

This is the top level concept provided by the *Country Module*.
Each country record in Tryton represents a specific country, political state
or nation.

The ISO 3166 standard defines the codes and names of countries and is used when
`Loading and updating countries and subdivisions`.

.. seealso::

   Countries can be found under the main menu entry:

      |Administration --> Countries --> Countries|__

      .. |Administration --> Countries --> Countries| replace:: :menuselection:`Administration --> Countries --> Countries`
      __ https://demo.tryton.org/model/country.country

.. _model-country.subdivision:

Subdivision
===========

The *Subdivision* of a `Country <model-country.country>` represents a well
defined area of that country.
Subdivisions can be any size, ranging from regions, provinces, states, and
counties down to municipalities, cities and boroughs.

The ISO 3166-2 standard defines codes and names for country subdivisions.
These are automatically loaded and updated along with the countries.

.. _model-country.postal_code:

Postal Code
===========

The *Postal Code* concept is used to store postal codes, and their relationship
to `Countries <model-country.country>`, `Subdivisions
<model-country.subdivision>` and cities.
Depending on the country they relate to these codes are known locally as
either postcodes, post codes, :abbr:`PIN (Postal Index Number)` or
:abbr:`ZIP (Zone Improvement Plan)` codes.

A script is provided for `loading and updating postal codes`.
