==================
Tryton GIS backend
==================

Tryton GIS (`Geographic Information System
<https://en.wikipedia.org/wiki/Geographic_information_system>`_) adds support
for geospatial data to Tryton.
It adds new *Field types* like *Point*, *LineString* and *MultiPolygon*.

The intended use is to write GIS data directly into the database with an
`existing GIS software <https://en.wikipedia.org/wiki/PostGIS#Users>`_.

For using these Tryton GIS, the `PostGIS <https://postgis.net/>`_ extension
must be installed on the database and the database ``uri`` in the
``[database]`` sectionn of the configuration must start with: ``postgis://``
instead of ``postgresql://``.

.. toctree::
   :maxdepth: 2

   fields
   releases
