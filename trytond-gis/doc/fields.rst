.. _ref-models-gis_fields:
.. module:: trytond_gis.fields

======
Fields
======

The Tryton GIS backend provides the Field types described below.
They be used in a ModelSQL like this::

  from trytond.model import ModelSQL
  from trytond_gis.fields import Point


  class Point(ModelSQL):
      __name__ = 'test.gis.point'

      point = Point("Point")

.. contents::
   :local:
   :backlinks: entry
   :depth: 2

Geometry field types
====================

Geometry
--------

.. class:: Geometry([string[, dimension[, \**options]]])

   The base class of all other geometry field types defined here.

.. attribute:: Geometry.dimension

   The number of dimension of the geometry.

Point
-----

.. class:: Point(\**options)

   A subclass of :class:`Geometry` used to store a point.

LineString
----------

.. class:: LineString(\**options)

   A subclass of :class:`Geometry` used to store a linestring.

Polygon
-------

.. class:: Polygon(\**options)

   A subclass of :class:`Geometry` used to store a polygon.

MultiPoint
-----------

.. class:: MultiPoint(\**options)

   A subclass of :class:`Geometry` used to store a collection of points.

MultiLineString
---------------

.. class:: MultiLineString(\**options)

   A subclass of :class:`Geometry` used to store a collection of linestrings.

MultiPolygon
------------

.. class:: MultiPolygon(\**options)

   A subclass of :class:`Geometry` used to store a collection of polygon.

GeometryCollection
------------------

.. class:: GeometryCollection(\**options)

   A subclass of :class:`Geometry` used to store a collection of any geometry.
