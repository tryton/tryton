# This file is part of trytond_gis.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from sql import Null
from sql.operators import Not
from trytond import backend
from trytond.model import fields
from trytond.model.fields.field import SQL_OPERATORS

from trytond_gis import _GeoJSON, sql as geo_sql

GEOGRAPHIC_OPERATORS = {
    '=': geo_sql.ST_Equals,
    '!=': lambda l, r: Not(geo_sql.ST_Equals(l, r)),
    }


class Geometry(fields.Field):
    _type = 'geometry'
    _geometry_type = 'GEOMETRY'

    def __init__(self, string="", dimension=2, loading='lazy', **kwargs):
        super(Geometry, self).__init__(
            string=string, loading=loading, **kwargs)
        self.dimension = dimension

    @property
    def _sql_type(self):
        assert backend.name in {'postgis'}
        return 'GIS_%s(%s)' % (
            self._geometry_type, self.dimension)

    def sql_format(self, value):
        if isinstance(value, dict):
            return _GeoJSON(value)
        return super(Geometry, self).sql_format(value)

    def convert_domain(self, domain, tables, Model):
        table, _ = tables[None]
        name, operator, value = domain

        assert operator in GEOGRAPHIC_OPERATORS

        column = self.sql_column(table)

        if operator in {'=', '!='} and value is Null:
            Operator = SQL_OPERATORS[operator]
            return Operator(column, Null)
        Operator = GEOGRAPHIC_OPERATORS[operator]
        expression = Operator(column, self._domain_value(operator, value))

        return expression

    def definition(self, model, language):
        definition = super().definition(model, language)
        definition['dimension'] = self.dimension
        definition['geometry_type'] = self.geometry_type
        return definition


class Point(Geometry):
    _geometry_type = 'POINT'


class LineString(Geometry):
    _geometry_type = 'LINESTRING'


class Polygon(Geometry):
    _geometry_type = 'POLYGON'


class MultiPoint(Geometry):
    _geometry_type = 'MULTIPOINT'


class MultiLineString(Geometry):
    _geometry_type = 'MULTILINESTRING'


class MultiPolygon(Geometry):
    _geometry_type = 'MULTIPOLYGON'


class GeometryCollection(Geometry):
    _geometry_type = 'GEOMETRYCOLLECTION'
