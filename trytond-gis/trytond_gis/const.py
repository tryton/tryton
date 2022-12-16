# This file is part of trytond_gis.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import re

WGS_84 = 4326
GIS_SQL_TYPE_RE = re.compile(
    r'GIS_(?P<type>[A-Z]+)\((?P<dimension>[0-9]+)\)')
