# This file is part of trytond_gis.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL
from trytond_gis import fields as geo_fields

__all__ = ['Point']


class Point(ModelSQL):
    'Point'
    __name__ = 'test.gis.point'

    point = geo_fields.Point('Point')
